# scrapers/litellm_source.py
#
# Consumes BerriAI/litellm's community-maintained model_prices_and_context_window.json
# as the primary source of price data for our pricing.json.
#
# Why: vendor pricing pages (Anthropic/OpenAI/Google) are all JS-rendered SPAs;
# our DOM-based scrapers extract model metadata but fail on prices. litellm
# tracks the same data, is updated near-daily by the community, and is MIT.
#
# Output shape: {provider_key: {canonical_id: pricing_dict}}
# where pricing_dict matches pricing-data's existing _make_empty_pricing schema
# (input_per_1m_tokens, output_per_1m_tokens, cache_write/cache_read, ...).
#
# See plan v5 §1 for the full rationale; this module owns:
#   - canonical id normalization (6 transforms)
#   - cross-provider field-level merge for the same canonical id
#   - skip prefixes for non-canonical providers (azure_ai/, openrouter/, ft:, etc.)
#   - debug counters surfaced to the audit step

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

LITELLM_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)
FETCH_TIMEOUT_S = 15

# Per our provider key, accepted litellm_provider values in priority order.
# Earlier entries win when a canonical_id is hit by multiple litellm rows.
_PROVIDER_ALLOWLIST: Dict[str, List[str]] = {
    "claude":   ["anthropic", "bedrock", "bedrock_converse", "vertex_ai-anthropic_models"],
    "openai":   ["openai"],                       # exclude azure, openrouter, fireworks, etc.
    "gemini":   ["gemini", "vertex_ai-language-models"],
    "deepseek": ["deepseek"],                     # 12 chat models with real prices in litellm
    # 豆包 (volcengine): litellm 当前 4 个 doubao-seed chat 入口都是 null 价格,
    # 但 model_id 注册可用. 价格通过 capabilities_fallback.PRICING_FALLBACK 填.
    # 注意 volcengine 命名空间下还混进非豆包 (deepseek-v3 / glm / kimi 被 volc
    # 托管转售), 在下面 _is_litellm_entry_for 里按 key prefix 过滤掉.
    "doubao":   ["volcengine"],
}

# Reverse: litellm_provider → our provider_key.
_REVERSE_PROVIDER: Dict[str, str] = {
    lit: our
    for our, lits in _PROVIDER_ALLOWLIST.items()
    for lit in lits
}

# Priority weight (lower wins) for each litellm_provider.
_PROVIDER_PRIORITY: Dict[str, int] = {}
for _our_key, _lits in _PROVIDER_ALLOWLIST.items():
    for _i, _lit in enumerate(_lits):
        _PROVIDER_PRIORITY[_lit] = _i

# Skip entries whose key has any of these prefixes — never canonical chat models.
# `deepseek/` was previously skipped; now allowed since we opted DeepSeek into
# `_PROVIDER_ALLOWLIST`. `volcengine/` allowed for the doubao subset, gated by
# `_is_litellm_entry_for` below.
_KEY_SKIP_PREFIXES = (
    "ft:", "azure/", "azure_ai/", "openrouter/", "groq/",
    "fireworks_ai/", "together_ai/", "perplexity/",
    "anyscale/", "replicate/", "ollama/", "ollama_chat/",
    "huggingface/", "watsonx/",
)


def _is_litellm_entry_for(provider_key: str, raw_key: str) -> bool:
    """Extra filter for providers whose litellm namespace mixes families.

    volcengine hosts doubao, glm, kimi, deepseek-v3 etc. as a multi-tenant
    inference platform — but we only want our `doubao` provider entry to claim
    doubao-prefixed models. Other namespaces in litellm map 1:1 to providers,
    so they pass through unchanged.
    """
    if provider_key == "doubao":
        # Match both bare `doubao-*` and `volcengine/doubao-*` shapes.
        lk = raw_key.lower()
        return lk.startswith("doubao-") or lk.startswith("volcengine/doubao-")
    return True

_REGIONAL_RE = re.compile(r"^(us|eu|apac|jp|au|global|sa|me|af|ca|in)\.")
_VERSION_RE = re.compile(r"-v\d+(:\d+)?$")
_LATEST_RE = re.compile(r"-latest$")


def _canonicalize(key: str) -> str:
    """Normalize a litellm key into a flat canonical model_id.

    Idempotent: f(f(x)) == f(x). See plan §1 for the 6 transforms.
    """
    s = key
    is_bedrock_family = False  # gate -v\d suffix strip to bedrock/anthropic only
    # 1. Strip provider-namespace prefixes (gemini/, vertex_ai/, deepseek/, volcengine/)
    for prefix in ("gemini/", "vertex_ai/", "deepseek/", "volcengine/"):
        if s.startswith(prefix):
            s = s[len(prefix):]
            break
    # 2. Strip bedrock/ wrapper
    if s.startswith("bedrock/"):
        s = s[len("bedrock/"):]
        is_bedrock_family = True
    # 3. Strip leading regional bedrock segment (us. eu. etc.)
    if _REGIONAL_RE.match(s):
        is_bedrock_family = True
    s = _REGIONAL_RE.sub("", s)
    # 4. Strip anthropic. namespace (after regional)
    if s.startswith("anthropic."):
        s = s[len("anthropic."):]
        is_bedrock_family = True
    # 5. Replace @ with - (Vertex Anthropic uses claude-3-5-sonnet@20240620)
    s = s.replace("@", "-")
    # 6. Strip trailing -v\d+(:\d+)? suffix (Bedrock revision tag). ONLY for
    #    bedrock-family keys — DeepSeek's own model ids like `deepseek-v3` use
    #    the same syntax to mean "model version 3" and we must NOT strip those.
    if is_bedrock_family:
        s = _VERSION_RE.sub("", s)
    # 7. Strip trailing -latest (aliases keep their bare-id form)
    s = _LATEST_RE.sub("", s)
    return s


def _convert_pricing(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Map litellm price keys (per-token) to pricing-data schema (per-1M).

    Return type is `Dict[str, Any]` (not narrowed to Optional[float]) because
    the dict also carries the string `currency`, `notes`, and the internal
    `_litellm_providers_seen` list that _accumulate stashes.
    """
    def per_m(token_key: str) -> Optional[float]:
        v = entry.get(token_key)
        if v is None:
            return None
        try:
            return round(float(v) * 1_000_000, 6)
        except (TypeError, ValueError):
            return None

    out: Dict[str, Any] = {
        "currency": "USD",
        "input_per_1m_tokens": per_m("input_cost_per_token"),
        "input_per_1m_tokens_above_200k": per_m("input_cost_per_token_above_200k_tokens"),
        "output_per_1m_tokens": per_m("output_cost_per_token"),
        "cache_write_per_1m_tokens": per_m("cache_creation_input_token_cost"),
        "cache_read_per_1m_tokens": per_m("cache_read_input_token_cost"),
        "notes": "",
    }
    return out


def _has_any_price(pricing: Dict[str, Any]) -> bool:
    return any(
        pricing.get(k) is not None
        for k in (
            "input_per_1m_tokens", "input_per_1m_tokens_above_200k",
            "output_per_1m_tokens", "cache_write_per_1m_tokens",
            "cache_read_per_1m_tokens",
        )
    )


def _accumulate(
    out_provider: Dict[str, Dict[str, Any]],
    canonical_id: str,
    new_pricing: Dict[str, Any],
    new_litellm_provider: str,
) -> None:
    """Field-level cross-entry merge for the same canonical_id.

    For each price field: prefer non-None; on a both-non-None conflict, the
    value from the higher-priority litellm_provider (lower index in the
    allowlist) wins. Records `_litellm_providers_seen` for the cross-validation
    audit so we know if multiple providers contributed.
    """
    existing = out_provider.get(canonical_id)
    if existing is None:
        # First sighting — accept as-is and tag the provider.
        new_pricing["_litellm_providers_seen"] = [new_litellm_provider]
        out_provider[canonical_id] = new_pricing
        return

    new_priority = _PROVIDER_PRIORITY.get(new_litellm_provider, 999)
    existing_providers = existing.get("_litellm_providers_seen") or []
    existing_priority = min(
        (_PROVIDER_PRIORITY.get(p, 999) for p in existing_providers),
        default=999,
    )

    # Field-level merge:
    for field in (
        "input_per_1m_tokens", "input_per_1m_tokens_above_200k",
        "output_per_1m_tokens", "cache_write_per_1m_tokens",
        "cache_read_per_1m_tokens",
    ):
        new_v = new_pricing.get(field)
        old_v = existing.get(field)
        if new_v is None:
            continue
        if old_v is None:
            existing[field] = new_v
        else:
            # Both non-None — keep the higher-priority entry's value.
            if new_priority < existing_priority:
                existing[field] = new_v

    if new_litellm_provider not in existing_providers:
        existing_providers.append(new_litellm_provider)
    existing["_litellm_providers_seen"] = existing_providers


def fetch_litellm_prices(
    *,
    url: str = LITELLM_URL,
    timeout_s: int = FETCH_TIMEOUT_S,
) -> Tuple[Dict[str, Dict[str, Dict[str, Any]]], Dict[str, Any]]:
    """Fetch + parse + normalize litellm's pricing JSON.

    Returns (data, counters):
      data:     {our_provider_key: {canonical_id: pricing_dict}}
                where pricing_dict has the per-1M fields + `source: "litellm"`.
      counters: stats useful for audit/debug — skipped reasons + per-provider hits.

    On total failure (network/parse/HTTP), returns ({}, counters with
    `fetch_succeeded: False`).
    """
    counters: Dict[str, Any] = {
        "fetch_succeeded": False,
        "fetch_latency_s": 0.0,
        "total_entries": 0,
        "skipped_non_dict": 0,
        "skipped_prefix": 0,
        "skipped_non_chat": 0,
        "skipped_no_provider": 0,
        "unrecognized_provider": 0,
        "kept": 0,
        "by_provider": {k: 0 for k in _PROVIDER_ALLOWLIST},
        "providers_seen": {},  # litellm_provider → kept count
    }

    t0 = time.time()
    try:
        resp = requests.get(url, timeout=timeout_s)
        resp.raise_for_status()
        litellm_json = resp.json()
    except Exception as exc:
        counters["fetch_latency_s"] = round(time.time() - t0, 3)
        counters["error"] = f"{type(exc).__name__}: {exc}"
        logger.warning("fetch_litellm_prices failed: %s", exc)
        return {}, counters

    counters["fetch_succeeded"] = True
    counters["fetch_latency_s"] = round(time.time() - t0, 3)
    counters["total_entries"] = len(litellm_json)

    out: Dict[str, Dict[str, Dict[str, Any]]] = {k: {} for k in _PROVIDER_ALLOWLIST}

    for raw_key, entry in litellm_json.items():
        if raw_key == "sample_spec":
            continue
        if not isinstance(entry, dict):
            counters["skipped_non_dict"] += 1
            continue
        if any(raw_key.startswith(p) for p in _KEY_SKIP_PREFIXES):
            counters["skipped_prefix"] += 1
            continue
        if entry.get("mode") != "chat":
            counters["skipped_non_chat"] += 1
            continue
        provider = entry.get("litellm_provider")
        if not provider:
            counters["skipped_no_provider"] += 1
            continue
        our_key = _REVERSE_PROVIDER.get(provider)
        if our_key is None:
            counters["unrecognized_provider"] += 1
            continue

        if not _is_litellm_entry_for(our_key, raw_key):
            counters["skipped_namespace_mismatch"] = counters.get(
                "skipped_namespace_mismatch", 0
            ) + 1
            continue

        canonical_id = _canonicalize(raw_key)
        if not canonical_id:
            continue

        pricing = _convert_pricing(entry)
        _accumulate(out[our_key], canonical_id, pricing, provider)
        counters["kept"] += 1
        counters["by_provider"][our_key] += 1
        counters["providers_seen"][provider] = counters["providers_seen"].get(provider, 0) + 1

    # Drop canonical_ids whose accumulated pricing is still all-None
    # (e.g. litellm entry had only `max_tokens` and no price fields).
    for our_key, models in out.items():
        out[our_key] = {
            cid: p for cid, p in models.items() if _has_any_price(p)
        }

    # Tag source on each retained entry; strip the internal tracker so
    # downstream sees a clean pricing dict.
    for our_key, models in out.items():
        for cid, p in models.items():
            providers_seen = p.pop("_litellm_providers_seen", [])
            p["source"] = "litellm"
            if len(providers_seen) > 1:
                p["source_detail"] = sorted(providers_seen)

    return out, counters
