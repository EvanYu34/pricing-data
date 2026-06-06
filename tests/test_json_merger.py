"""Unit tests for utils.json_merger v5 field-level merge."""
from __future__ import annotations

import pytest

from utils import JsonMerger


def _empty_pricing():
    return {
        "currency": "USD",
        "input_per_1m_tokens": None,
        "input_per_1m_tokens_above_200k": None,
        "output_per_1m_tokens": None,
        "cache_write_per_1m_tokens": None,
        "cache_read_per_1m_tokens": None,
        "notes": "",
    }


def _model(model_id, **overrides):
    base = {
        "model_id": model_id,
        "display_name": model_id,
        "context_window_tokens": 200000,
        "capabilities": ["text_generation"],
        "pricing": _empty_pricing(),
        "is_deprecated": False,
        "notes": "",
        "multilingual": True,
        "api_endpoints": [],
    }
    base.update(overrides)
    return base


def _provider_block(*models):
    return {
        "fetch_status": "success",
        "error_message": None,
        "provider_info": {"name": "Anthropic"},
        "models": list(models),
    }


def _existing(*models, last_updated="2026-03-01T00:00:00Z"):
    return {
        "last_updated": last_updated,
        "schema_version": "2.0",
        "sources": {"claude": _provider_block(*models)},
    }


# Test 1: new has full pricing → new wins
def test_new_full_pricing_wins():
    old = _existing(_model("claude-sonnet-4-5", source="scraper"))
    new = {
        "claude": _provider_block(_model(
            "claude-sonnet-4-5",
            pricing={**_empty_pricing(), "input_per_1m_tokens": 3.0, "output_per_1m_tokens": 15.0},
            source="litellm",
        )),
    }
    merged = JsonMerger().merge(old, new)
    m = merged["sources"]["claude"]["models"][0]
    assert m["pricing"]["input_per_1m_tokens"] == 3.0
    assert m["source"] == "litellm"


# Test 2: old has full pricing, new returns all-None, scraper still sees model → stale
def test_new_all_none_marks_stale():
    old = _existing(_model(
        "claude-sonnet-4-5",
        pricing={**_empty_pricing(), "input_per_1m_tokens": 3.0, "output_per_1m_tokens": 15.0},
        source="litellm",
    ))
    new = {
        "claude": _provider_block(_model("claude-sonnet-4-5", pricing=_empty_pricing())),
    }
    merged = JsonMerger().merge(old, new)
    m = merged["sources"]["claude"]["models"][0]
    # Old price preserved
    assert m["pricing"]["input_per_1m_tokens"] == 3.0
    # Marked as stale
    assert m["source"] == "stale"


# Test 3: partial fields each side → merged
def test_partial_fields_merge():
    old = _existing(_model(
        "claude-sonnet-4-5",
        pricing={**_empty_pricing(), "input_per_1m_tokens": 3.0, "output_per_1m_tokens": None},
        source="scraper",
    ))
    new = {
        "claude": _provider_block(_model(
            "claude-sonnet-4-5",
            pricing={**_empty_pricing(), "input_per_1m_tokens": None, "output_per_1m_tokens": 15.0},
            source="litellm",
        )),
    }
    merged = JsonMerger().merge(old, new)
    m = merged["sources"]["claude"]["models"][0]
    assert m["pricing"]["input_per_1m_tokens"] == 3.0
    assert m["pricing"]["output_per_1m_tokens"] == 15.0
    assert m["source"] == "merged"


# Test 4: old has model, new doesn't include it → preserve, no last_seen_run change
def test_model_dropped_from_new_preserved():
    old = _existing(
        _model("claude-sonnet-4-5",
               pricing={**_empty_pricing(), "input_per_1m_tokens": 3.0},
               source="litellm", last_seen_run="2026-04-01"),
        _model("claude-deprecated-old",
               pricing={**_empty_pricing(), "input_per_1m_tokens": 1.0},
               source="litellm", last_seen_run="2026-02-15"),
    )
    new = {
        "claude": _provider_block(_model("claude-sonnet-4-5",
                                          pricing={**_empty_pricing(), "input_per_1m_tokens": 3.0},
                                          source="litellm")),
    }
    merged = JsonMerger().merge(old, new)
    models = {m["model_id"]: m for m in merged["sources"]["claude"]["models"]}
    assert "claude-deprecated-old" in models
    # last_seen_run preserved (not updated to today)
    assert models["claude-deprecated-old"]["last_seen_run"] == "2026-02-15"


# Test 5: new has model, old doesn't → add with last_seen_run=today
def test_new_model_added():
    old = _existing(_model("claude-sonnet-4-5"))
    new = {
        "claude": _provider_block(
            _model("claude-sonnet-4-5"),
            _model("claude-brand-new",
                   pricing={**_empty_pricing(), "input_per_1m_tokens": 5.0}, source="litellm"),
        ),
    }
    merged = JsonMerger().merge(old, new)
    models = {m["model_id"]: m for m in merged["sources"]["claude"]["models"]}
    assert "claude-brand-new" in models
    # last_seen_run should be ISO date (today)
    assert len(models["claude-brand-new"]["last_seen_run"]) == 10


# Test 6: scrape failed → preserve old block wholesale
def test_failed_fetch_preserves_old():
    old = _existing(_model("claude-sonnet-4-5",
                            pricing={**_empty_pricing(), "input_per_1m_tokens": 3.0}))
    new = {
        "claude": {"fetch_status": "failed", "error_message": "oops",
                   "provider_info": {}, "models": []},
    }
    merged = JsonMerger().merge(old, new)
    block = merged["sources"]["claude"]
    assert block["fetch_status"] == "failed"
    assert block["error_message"] == "oops"
    assert block["models"][0]["pricing"]["input_per_1m_tokens"] == 3.0


# Test 7: legacy old (no source / no last_seen_run) → defaults applied
def test_legacy_bootstrap():
    # Model has no `source` and no `last_seen_run` (legacy schema)
    old = {
        "last_updated": "2026-03-01T00:00:00Z",
        "schema_version": "2.0",
        "sources": {"claude": {
            "fetch_status": "success",
            "models": [{
                "model_id": "claude-sonnet-4-5",
                "pricing": {**_empty_pricing(), "input_per_1m_tokens": 3.0},
                # no source field, no last_seen_run
            }],
        }},
    }
    new = {
        "claude": _provider_block(_model("claude-sonnet-4-5", pricing=_empty_pricing())),
    }
    merged = JsonMerger().merge(old, new)
    m = merged["sources"]["claude"]["models"][0]
    # Pricing preserved (new is all-None, old has price)
    assert m["pricing"]["input_per_1m_tokens"] == 3.0
    # Source marked stale (new sees the model but no price)
    assert m["source"] == "stale"
    # last_seen_run from current run (model was in new)
    assert len(m["last_seen_run"]) == 10


# Test 8: capabilities_fallback model with no price both sides → "fallback"
def test_fallback_exempt():
    # claude-opus-4-6 IS in capabilities_fallback per the real file.
    old = _existing(_model("claude-opus-4-6", pricing=_empty_pricing()))
    new = {
        "claude": _provider_block(_model("claude-opus-4-6", pricing=_empty_pricing())),
    }
    merged = JsonMerger().merge(old, new)
    m = merged["sources"]["claude"]["models"][0]
    # No price anywhere → fallback (because the model_id is in fallback list)
    assert m["source"] == "fallback"


# Test 9a (#4): last_verified_at + verified_source set when new run hits the model
def test_last_verified_at_set_on_hit():
    old = _existing(_model("claude-sonnet-4-5", source="scraper"))
    new = {
        "claude": _provider_block(_model(
            "claude-sonnet-4-5",
            pricing={**_empty_pricing(), "input_per_1m_tokens": 3.0},
            source="litellm",
        )),
    }
    merged = JsonMerger().merge(old, new)
    m = merged["sources"]["claude"]["models"][0]
    # ISO timestamp (full, not just date)
    assert m["last_verified_at"] is not None
    assert "T" in m["last_verified_at"] and m["last_verified_at"].endswith("Z")
    assert m["verified_source"] == "litellm"


# Test 9b (#4): last_verified_at preserved when model not in this run's data
def test_last_verified_at_preserved_on_miss():
    old = _existing(
        _model("claude-sonnet-4-5",
               last_verified_at="2026-04-01T12:00:00Z",
               verified_source="litellm"),
        _model("claude-deprecated-old",
               last_verified_at="2026-02-15T08:30:00Z",
               verified_source="scraper",
               pricing={**_empty_pricing(), "input_per_1m_tokens": 1.0}),
    )
    # New run only has claude-sonnet-4-5, missing claude-deprecated-old
    new = {
        "claude": _provider_block(_model("claude-sonnet-4-5", source="litellm")),
    }
    merged = JsonMerger().merge(old, new)
    models = {m["model_id"]: m for m in merged["sources"]["claude"]["models"]}
    # Preserved model keeps its old last_verified_at + verified_source untouched
    assert models["claude-deprecated-old"]["last_verified_at"] == "2026-02-15T08:30:00Z"
    assert models["claude-deprecated-old"]["verified_source"] == "scraper"


# Test 9c (#4): legacy entries (no last_verified_at) bootstrap to None on miss,
# get filled on hit
def test_last_verified_at_legacy_bootstrap():
    # Legacy old has neither last_verified_at nor verified_source
    old = {
        "last_updated": "2026-03-01T00:00:00Z",
        "schema_version": "2.0",
        "sources": {"claude": {
            "fetch_status": "success",
            "models": [
                {"model_id": "claude-hit",     "pricing": _empty_pricing()},
                {"model_id": "claude-no-hit",  "pricing": _empty_pricing()},
            ],
        }},
    }
    # claude-hit gets hit this run; claude-no-hit dropped from new
    new = {
        "claude": _provider_block(_model("claude-hit", source="litellm")),
    }
    merged = JsonMerger().merge(old, new)
    models = {m["model_id"]: m for m in merged["sources"]["claude"]["models"]}
    # Hit → filled in
    assert models["claude-hit"]["last_verified_at"] is not None
    assert models["claude-hit"]["verified_source"] == "litellm"
    # Miss + legacy → both None (no info to preserve)
    assert models["claude-no-hit"]["last_verified_at"] is None
    assert models["claude-no-hit"]["verified_source"] is None


# Test 9d (#5): PRICING_FALLBACK fills in when both old + new have no pricing,
# and only when the model_id is actually in the fallback dict
def test_pricing_fallback_fills_when_both_sides_empty():
    # gemini-1.5-pro IS in the new PRICING_FALLBACK (verified via capabilities_fallback.PRICING_FALLBACK).
    # Both old + new give empty pricing → fallback should kick in.
    old = {
        "last_updated": "2026-03-01T00:00:00Z",
        "schema_version": "2.0",
        "sources": {"gemini": {
            "fetch_status": "success",
            "models": [{"model_id": "gemini-1.5-pro", "pricing": _empty_pricing()}],
        }},
    }
    new = {
        "gemini": {
            "fetch_status": "success",
            "models": [{"model_id": "gemini-1.5-pro", "pricing": _empty_pricing()}],
        },
    }
    merged = JsonMerger().merge(old, new)
    m = merged["sources"]["gemini"]["models"][0]
    # Fallback pricing should be present
    assert m["pricing"]["input_per_1m_tokens"] == 1.25
    assert m["pricing"]["output_per_1m_tokens"] == 5.00


def test_pricing_fallback_does_not_overwrite_real_price():
    # If new pricing exists, fallback must NOT touch it.
    old = {
        "last_updated": "2026-03-01T00:00:00Z",
        "schema_version": "2.0",
        "sources": {"gemini": {"fetch_status": "success", "models": []}},
    }
    new = {
        "gemini": {
            "fetch_status": "success",
            "models": [{
                "model_id": "gemini-1.5-pro",
                "pricing": {**_empty_pricing(), "input_per_1m_tokens": 999.99},
            }],
        },
    }
    merged = JsonMerger().merge(old, new)
    m = merged["sources"]["gemini"]["models"][0]
    # Real (fake-test) price preserved, fallback didn't touch
    assert m["pricing"]["input_per_1m_tokens"] == 999.99


# Test 10: diff_summary still works on the new schema
def test_diff_summary_compatibility():
    old = _existing(_model("model-a"), _model("model-b"))
    new = {
        "claude": _provider_block(_model("model-a"), _model("model-c")),
    }
    merged = JsonMerger().merge(old, new)
    summary = JsonMerger.diff_summary(old, merged)
    # `model-c` is new, `model-b` is preserved (so still present in merged)
    assert "claude" in summary["added_models"]
    assert "model-c" in summary["added_models"]["claude"]
    # `model-b` is preserved per merger rules, so NOT removed
    assert "claude" not in summary.get("removed_models", {})
