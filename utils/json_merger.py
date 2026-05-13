# utils/json_merger.py
#
# Merges freshly scraped provider data with the previously stored pricing.json.
#
# v5 (M6) — field-level prefer-non-None merge with source attribution and
# last_seen_run bookkeeping. Replaces the prior wholesale block-replace logic
# which would silently overwrite real prices with None.
#
# Rules per model (see _merge_model below):
#   pricing.* fields  : prefer non-None new; preserve non-None old
#   capabilities[]    : prefer new when present; else old
#   scalar metadata   : prefer new when present; else old
#   `source`          : derived from which side supplied prices (5-tier priority)
#   `last_seen_run`   : today if model present in new; else preserve old
#
# Per provider:
#   - If new fetch_status != "success" → preserve old block wholesale.
#   - Else iterate union of model_ids, applying _merge_model.

import copy
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "2.0"

PRICING_FIELDS = (
    "input_per_1m_tokens",
    "input_per_1m_tokens_above_200k",
    "output_per_1m_tokens",
    "cache_write_per_1m_tokens",
    "cache_read_per_1m_tokens",
)


def _utc_today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_fallback_model_ids() -> Dict[str, Set[str]]:
    """Return {provider_key: set(model_ids)} of human-curated fallback entries.

    Used during bootstrap migration: legacy pricing.json entries whose model_id
    appears in this set get tagged source="fallback" instead of "scraper", so
    the audit's fallback-exemption fires immediately on the first run.
    """
    try:
        from scrapers.capabilities_fallback import CAPABILITIES_FALLBACK
    except ImportError:
        logger.warning("Could not import capabilities_fallback; assuming no fallback ids")
        return {}
    return {
        provider: set(model_dict.keys())
        for provider, model_dict in CAPABILITIES_FALLBACK.items()
    }


def _has_any_price(pricing: Dict[str, Any]) -> bool:
    """True if any of the canonical pricing fields is non-None."""
    if not pricing:
        return False
    return any(pricing.get(k) is not None for k in PRICING_FIELDS)


def _non_none_keys(pricing: Dict[str, Any]) -> Set[str]:
    if not pricing:
        return set()
    return {k for k in PRICING_FIELDS if pricing.get(k) is not None}


def _merge_pricing(
    old_p: Dict[str, Any],
    new_p: Dict[str, Any],
) -> Dict[str, Any]:
    """Field-level merge: prefer non-None new; preserve non-None old."""
    out: Dict[str, Any] = {}
    # currency: prefer new, else old, else default USD
    out["currency"] = new_p.get("currency") or old_p.get("currency") or "USD"
    for field in PRICING_FIELDS:
        new_v = new_p.get(field)
        old_v = old_p.get(field)
        out[field] = new_v if new_v is not None else old_v
    # notes: prefer new (non-empty), else old
    out["notes"] = (new_p.get("notes") or old_p.get("notes") or "").strip()
    return out


def _derive_source(
    old_model: Optional[Dict[str, Any]],
    new_model: Optional[Dict[str, Any]],
    merged_pricing: Dict[str, Any],
    fallback_ids: Set[str],
    *,
    new_seen: bool,
) -> str:
    """5-tier source derivation. See plan §2 for the priority ladder."""
    old_p = (old_model or {}).get("pricing") or {}
    new_p = (new_model or {}).get("pricing") or {}
    new_keys = _non_none_keys(new_p)
    old_keys = _non_none_keys(old_p)

    # Priority 1: both sides contributed different fields → merged
    if new_keys and old_keys and (new_keys != old_keys) and (new_keys & old_keys != old_keys | new_keys):
        # Some field is supplied by only one side AND the sides supply non-identical sets
        contributing_sides = (len(new_keys - old_keys) > 0) and (len(old_keys - new_keys) > 0)
        if contributing_sides:
            return "merged"

    # Priority 2: new pricing has any non-None field → new["source"] (typically "litellm")
    if new_keys:
        return (new_model or {}).get("source") or "litellm"

    # Priority 3: old had pricing, new returned all-None, but scraper still sees the model
    if old_keys and new_seen:
        return "stale"

    # Priority 4: old has pricing, model dropped from scraper too → preserve old source
    if old_keys and not new_seen:
        return (old_model or {}).get("source") or "scraper"

    # Priority 5: no pricing on either side
    model_id = (new_model or old_model or {}).get("model_id", "")
    if model_id in fallback_ids:
        return "fallback"
    return (new_model or old_model or {}).get("source") or "scraper"


def _merge_model(
    old_model: Optional[Dict[str, Any]],
    new_model: Optional[Dict[str, Any]],
    today: str,
    bootstrap_seed: str,
    fallback_ids: Set[str],
) -> Dict[str, Any]:
    """Combine an old and/or new model record into one merged record.

    `bootstrap_seed` is the existing pricing.json's top-level `last_updated`,
    used to seed `last_seen_run` for legacy entries that don't have one.
    """
    # Pick whichever has the data we need
    base = copy.deepcopy(new_model or old_model or {})
    other = old_model if new_model else (new_model or {})

    # Model_id should always be present (it's the union key)
    model_id = base.get("model_id") or (other or {}).get("model_id", "")
    base["model_id"] = model_id

    # display_name + scalar metadata: prefer new, else old
    for field in ("display_name", "context_window_tokens", "multilingual", "is_deprecated", "notes"):
        if base.get(field) in (None, "", []) and (other or {}).get(field) not in (None, "", []):
            base[field] = other[field]

    # capabilities[], api_endpoints[]: prefer new when non-empty; else old
    for field in ("capabilities", "api_endpoints"):
        if not base.get(field) and (other or {}).get(field):
            base[field] = copy.deepcopy(other[field])

    # Pricing: field-level merge
    old_p = (old_model or {}).get("pricing") or {}
    new_p = (new_model or {}).get("pricing") or {}
    base["pricing"] = _merge_pricing(old_p, new_p)

    # source: derive via 5-tier priority
    new_seen = new_model is not None
    base["source"] = _derive_source(
        old_model, new_model, base["pricing"], fallback_ids, new_seen=new_seen
    )

    # last_seen_run:
    #   - present in new this run → today
    #   - else preserve old's value (untouched)
    #   - bootstrap: legacy entry without the field → seed from old top-level last_updated
    if new_seen:
        base["last_seen_run"] = today
    else:
        base["last_seen_run"] = (
            (old_model or {}).get("last_seen_run") or bootstrap_seed
        )

    return base


class JsonMerger:
    """Merges new scraping results with existing pricing data (v5 semantics)."""

    def merge(
        self,
        existing: Dict[str, Any],
        new_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        today = _utc_today_iso()
        now = _utc_now_iso()

        # Bootstrap seed: use old top-level last_updated for legacy entries
        # whose `last_seen_run` field is missing. Falls back to "1970-01-01"
        # only if the old file truly lacks any timestamp.
        old_last_updated = existing.get("last_updated", "1970-01-01T00:00:00Z")
        bootstrap_seed = old_last_updated[:10] if old_last_updated else "1970-01-01"

        fallback_ids_by_provider = _load_fallback_model_ids()

        merged: Dict[str, Any] = {
            "last_updated": now,
            "schema_version": SCHEMA_VERSION,
            "attribution": {
                "litellm": "https://github.com/BerriAI/litellm — MIT",
            },
            "sources": {},
        }

        existing_sources: Dict[str, Any] = existing.get("sources", {})

        for provider, provider_data in new_results.items():
            fallback_ids = fallback_ids_by_provider.get(provider, set())

            if provider_data.get("fetch_status") != "success" or not provider_data.get("models"):
                # New fetch failed → preserve old block wholesale, stamp failure metadata.
                if provider in existing_sources:
                    old_block = copy.deepcopy(existing_sources[provider])
                    old_block["fetch_status"] = "failed"
                    old_block["error_message"] = provider_data.get("error_message") or (
                        "No models returned"
                        if provider_data.get("fetch_status") == "success"
                        else "Scrape failed; see logs"
                    )
                    merged["sources"][provider] = old_block
                    logger.warning(
                        "Merger: %s scrape failed; preserving %d old models",
                        provider, len(old_block.get("models", [])),
                    )
                else:
                    merged["sources"][provider] = provider_data
                    logger.warning("Merger: %s scrape failed and no previous data", provider)
                continue

            # Successful fetch → model-level pairwise merge.
            old_block = existing_sources.get(provider, {})
            old_models = {m["model_id"]: m for m in old_block.get("models", []) if "model_id" in m}
            new_models = {m["model_id"]: m for m in provider_data.get("models", []) if "model_id" in m}

            merged_model_list = []
            for model_id in sorted(set(old_models) | set(new_models)):
                merged_model_list.append(
                    _merge_model(
                        old_models.get(model_id),
                        new_models.get(model_id),
                        today=today,
                        bootstrap_seed=bootstrap_seed,
                        fallback_ids=fallback_ids,
                    )
                )

            out_block = {
                "fetch_status": "success",
                "error_message": None,
                "provider_info": provider_data.get("provider_info")
                                  or old_block.get("provider_info", {}),
                "models": merged_model_list,
            }
            merged["sources"][provider] = out_block
            logger.info(
                "Merger: %s merged → %d models (was %d, fresh %d)",
                provider, len(merged_model_list), len(old_models), len(new_models),
            )

        # Preserve providers present in old but absent from this run.
        for provider, old_data in existing_sources.items():
            if provider not in merged["sources"]:
                merged["sources"][provider] = copy.deepcopy(old_data)
                logger.info("Merger: %s preserved from previous (not in this run)", provider)

        return merged

    # ------------------------------------------------------------------
    # Diff helpers (unchanged interface — main.py:142 still calls this)
    # ------------------------------------------------------------------

    @staticmethod
    def diff_summary(
        old: Dict[str, Any],
        new: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Lightweight summary of changes between two pricing.json snapshots."""
        summary: Dict[str, Any] = {
            "added_models": {},
            "removed_models": {},
            "changed_prices": {},
            "failed_providers": [],
        }

        old_sources = old.get("sources", {})
        new_sources = new.get("sources", {})

        for provider in set(old_sources) | set(new_sources):
            new_pdata = new_sources.get(provider, {})
            old_pdata = old_sources.get(provider, {})

            if new_pdata.get("fetch_status") == "failed":
                summary["failed_providers"].append(provider)

            old_models: Dict[str, Any] = {
                m["model_id"]: m for m in old_pdata.get("models", []) if "model_id" in m
            }
            new_models: Dict[str, Any] = {
                m["model_id"]: m for m in new_pdata.get("models", []) if "model_id" in m
            }

            added = sorted(set(new_models) - set(old_models))
            removed = sorted(set(old_models) - set(new_models))
            changed: list = []

            for mid in set(old_models) & set(new_models):
                old_p = old_models[mid].get("pricing", {})
                new_p = new_models[mid].get("pricing", {})
                if old_p != new_p:
                    changed.append(mid)

            if added:
                summary["added_models"][provider] = added
            if removed:
                summary["removed_models"][provider] = removed
            if changed:
                summary["changed_prices"][provider] = sorted(changed)

        return summary
