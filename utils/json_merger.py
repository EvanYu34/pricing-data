# utils/json_merger.py
#
# Merges freshly scraped provider data with the previously stored pricing.json.
#
# Merge rules:
#   - If the new scrape for a provider succeeded → replace that provider's data.
#   - If the new scrape failed → keep the old model list intact but stamp the
#     updated fetch_status and error_message so clients know data may be stale.
#   - last_updated is always set to the current UTC timestamp.
#   - Any provider present in the old file but absent from the new run is kept
#     as-is (safety net against partial runs).

import copy
import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "2.0"


class JsonMerger:
    """Merges new scraping results with existing pricing data."""

    def merge(
        self,
        existing: Dict[str, Any],
        new_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Parameters
        ----------
        existing:
            The contents of the current pricing.json (may be empty dict on first run).
        new_results:
            Mapping of provider key → provider data block returned by each scraper's
            build_provider_data().

        Returns
        -------
        The merged pricing.json structure ready to be serialised.
        """
        merged: Dict[str, Any] = {
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "schema_version": SCHEMA_VERSION,
            "sources": {},
        }

        existing_sources: Dict[str, Any] = existing.get("sources", {})

        # Process providers returned by the current run
        for provider, provider_data in new_results.items():
            if provider_data.get("fetch_status") == "success" and provider_data.get("models"):
                # Fresh successful data → use it directly
                merged["sources"][provider] = provider_data
                logger.info(
                    "Merger: %s updated with %d models",
                    provider,
                    len(provider_data["models"]),
                )
            else:
                # Scrape failed (or returned no models) → fall back to old data
                if provider in existing_sources:
                    old_data = copy.deepcopy(existing_sources[provider])
                    old_data["fetch_status"] = "failed"
                    old_data["error_message"] = provider_data.get("error_message") or (
                        "No models returned by scraper"
                        if provider_data.get("fetch_status") == "success"
                        else "Scrape failed; see logs"
                    )
                    merged["sources"][provider] = old_data
                    logger.warning(
                        "Merger: %s scrape failed; preserving %d old models. Reason: %s",
                        provider,
                        len(old_data.get("models", [])),
                        old_data["error_message"],
                    )
                else:
                    # No fallback available — store the failed result as-is
                    merged["sources"][provider] = provider_data
                    logger.warning(
                        "Merger: %s scrape failed and no previous data available", provider
                    )

        # Preserve any providers that were in the old file but not in this run
        for provider, old_data in existing_sources.items():
            if provider not in merged["sources"]:
                merged["sources"][provider] = copy.deepcopy(old_data)
                logger.info("Merger: %s not in current run; preserved from previous data", provider)

        return merged

    # ------------------------------------------------------------------
    # Diff helpers (used by main.py for commit message generation)
    # ------------------------------------------------------------------

    @staticmethod
    def diff_summary(
        old: Dict[str, Any],
        new: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Return a lightweight summary of what changed between two pricing.json
        snapshots.  Used to decide whether a git commit is worth making and to
        build informative commit messages.

        Returns a dict with:
          added_models    : {provider: [model_id, ...]}
          removed_models  : {provider: [model_id, ...]}
          changed_prices  : {provider: [model_id, ...]}
          failed_providers: [provider, ...]
        """
        summary: Dict[str, Any] = {
            "added_models": {},
            "removed_models": {},
            "changed_prices": {},
            "failed_providers": [],
        }

        old_sources = old.get("sources", {})
        new_sources = new.get("sources", {})

        all_providers = set(old_sources) | set(new_sources)

        for provider in all_providers:
            new_pdata = new_sources.get(provider, {})
            old_pdata = old_sources.get(provider, {})

            if new_pdata.get("fetch_status") == "failed":
                summary["failed_providers"].append(provider)

            old_models: Dict[str, Any] = {
                m["model_id"]: m for m in old_pdata.get("models", [])
            }
            new_models: Dict[str, Any] = {
                m["model_id"]: m for m in new_pdata.get("models", [])
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
