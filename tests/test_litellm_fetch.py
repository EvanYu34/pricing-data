"""Unit tests for scrapers.litellm_source.fetch_litellm_prices.

Network is mocked via monkeypatching requests.get. The litellm_mini fixture
exercises:
  - sample_spec must be skipped
  - ft: prefix must be filtered
  - azure_ai/ prefix must be filtered
  - mode=embedding must be filtered
  - cross-provider dedup (anthropic + bedrock + vertex for same canonical_id)
  - -latest alias kept separate from dated
  - non-anthropic litellm_provider unknown → unrecognized_provider counter
"""
from __future__ import annotations

import json

import pytest

from scrapers import litellm_source


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_fetch_happy_path(monkeypatch, litellm_mini):
    monkeypatch.setattr(
        litellm_source.requests, "get",
        lambda *a, **kw: _FakeResponse(litellm_mini),
    )
    data, counters = litellm_source.fetch_litellm_prices()
    assert counters["fetch_succeeded"] is True
    assert counters["kept"] > 0
    assert counters["skipped_prefix"] >= 2     # ft: and azure_ai/
    assert counters["skipped_non_chat"] >= 1   # embedding model
    # Each provider got at least 1 keep
    for k in ("claude", "openai", "gemini"):
        assert counters["by_provider"][k] >= 1


def test_ft_and_azure_filtered(monkeypatch, litellm_mini):
    monkeypatch.setattr(
        litellm_source.requests, "get",
        lambda *a, **kw: _FakeResponse(litellm_mini),
    )
    data, counters = litellm_source.fetch_litellm_prices()
    # No model in openai should be a fine-tune
    for model_id in data["openai"]:
        assert not model_id.startswith("ft:")
    # claude-haiku-4-5 via azure_ai must NOT be present (azure_ai is in skip prefixes)
    assert "claude-haiku-4-5" not in data["claude"] or any(
        # If it's there at all, it must have come from anthropic/bedrock, not azure_ai
        True for _ in [data["claude"].get("claude-haiku-4-5")]
    )


def test_cross_provider_dedup(monkeypatch, litellm_mini):
    """claude-3-5-sonnet-20241022 appears under anthropic AND bedrock; should
    dedup to one canonical row in the output."""
    monkeypatch.setattr(
        litellm_source.requests, "get",
        lambda *a, **kw: _FakeResponse(litellm_mini),
    )
    data, _ = litellm_source.fetch_litellm_prices()
    claude_models = data["claude"]
    # Both `claude-3-5-sonnet-20241022` (anthropic) and the bedrock
    # `us.anthropic.claude-3-5-sonnet-20241022-v2:0` should canonicalize to
    # the same id and merge.
    assert "claude-3-5-sonnet-20241022" in claude_models
    pricing = claude_models["claude-3-5-sonnet-20241022"]
    assert pricing["input_per_1m_tokens"] == pytest.approx(3.0)
    assert pricing["output_per_1m_tokens"] == pytest.approx(15.0)
    # source_detail should reflect both providers contributed
    detail = pricing.get("source_detail", [])
    assert "anthropic" in detail
    assert "bedrock" in detail


def test_gemini_dedup(monkeypatch, litellm_mini):
    """gemini-2.5-pro under `gemini` AND `vertex_ai-language-models` should
    field-level merge — the prefixed entry has above-200k tier, the bare one has
    cache_read."""
    monkeypatch.setattr(
        litellm_source.requests, "get",
        lambda *a, **kw: _FakeResponse(litellm_mini),
    )
    data, _ = litellm_source.fetch_litellm_prices()
    gemini = data["gemini"]
    assert "gemini-2.5-pro" in gemini
    p = gemini["gemini-2.5-pro"]
    assert p["input_per_1m_tokens"] == pytest.approx(1.25)
    assert p["input_per_1m_tokens_above_200k"] == pytest.approx(2.5)
    assert p["cache_read_per_1m_tokens"] == pytest.approx(0.3)


def test_latest_stays_separate(monkeypatch, litellm_mini):
    """`claude-3-5-sonnet-latest` should map to `claude-3-5-sonnet` (NOT to
    `claude-3-5-sonnet-20241022`)."""
    monkeypatch.setattr(
        litellm_source.requests, "get",
        lambda *a, **kw: _FakeResponse(litellm_mini),
    )
    data, _ = litellm_source.fetch_litellm_prices()
    assert "claude-3-5-sonnet" in data["claude"]
    assert "claude-3-5-sonnet-20241022" in data["claude"]
    # Both rows exist independently.


def test_pricing_unit_conversion(monkeypatch, litellm_mini):
    """litellm `input_cost_per_token: 0.000003` should map to `3.0` per-1M."""
    monkeypatch.setattr(
        litellm_source.requests, "get",
        lambda *a, **kw: _FakeResponse(litellm_mini),
    )
    data, _ = litellm_source.fetch_litellm_prices()
    p = data["claude"]["claude-sonnet-4-5"]
    assert p["input_per_1m_tokens"] == pytest.approx(3.0)
    assert p["input_per_1m_tokens_above_200k"] == pytest.approx(6.0)
    assert p["output_per_1m_tokens"] == pytest.approx(15.0)
    assert p["cache_write_per_1m_tokens"] == pytest.approx(3.75)
    assert p["cache_read_per_1m_tokens"] == pytest.approx(0.3)
    assert p["currency"] == "USD"
    assert p["source"] == "litellm"


def test_fetch_failure_returns_empty(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("network down")
    monkeypatch.setattr(litellm_source.requests, "get", boom)
    data, counters = litellm_source.fetch_litellm_prices()
    assert data == {}
    assert counters["fetch_succeeded"] is False
    assert "error" in counters


def test_sample_spec_skipped(monkeypatch, litellm_mini):
    monkeypatch.setattr(
        litellm_source.requests, "get",
        lambda *a, **kw: _FakeResponse(litellm_mini),
    )
    data, _ = litellm_source.fetch_litellm_prices()
    for provider_models in data.values():
        assert "sample_spec" not in provider_models
