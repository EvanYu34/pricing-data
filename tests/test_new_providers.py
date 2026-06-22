"""Smoke tests for the DeepSeek + Doubao providers added in this PR.

Both are capabilities-only scrapers — no live fetch — so we just verify they
build a well-formed provider block from `capabilities_fallback`.
"""
from __future__ import annotations

import pytest

from scrapers import DeepSeekScraper, DoubaoScraper


def _assert_well_formed_provider(block: dict, expected_provider_name: str) -> None:
    assert block["fetch_status"] == "success"
    assert block["error_message"] is None
    info = block["provider_info"]
    assert info["name"] == expected_provider_name
    assert info["base_url"].startswith("https://")
    assert info["auth_method"]
    assert info["sdk_support"]
    models = block["models"]
    assert isinstance(models, list)
    assert models, "expected at least one fallback-registered model"
    for m in models:
        assert m["model_id"]
        assert m["display_name"]
        # context window must be a positive int (None would have failed earlier)
        assert isinstance(m["context_window_tokens"], int) and m["context_window_tokens"] > 0
        assert isinstance(m["capabilities"], list) and m["capabilities"]
        # pricing block exists even when prices null (litellm overlay fills it later)
        pricing = m["pricing"]
        assert pricing["currency"] == "USD"
        # endpoints present
        assert m["api_endpoints"]


def test_deepseek_provider_block_well_formed():
    block = DeepSeekScraper().build_provider_data()
    _assert_well_formed_provider(block, "DeepSeek")
    ids = {m["model_id"] for m in block["models"]}
    # The canonical ids that match litellm post-canonicalize (deepseek/ prefix
    # stripped + bedrock-family gate keeps -vN suffix intact).
    assert {"deepseek-chat", "deepseek-r1", "deepseek-v3", "deepseek-v4-pro"}.issubset(ids)


def test_doubao_provider_block_well_formed():
    block = DoubaoScraper().build_provider_data()
    _assert_well_formed_provider(block, "Doubao (Volcengine)")
    ids = {m["model_id"] for m in block["models"]}
    # All 4 Doubao Seed 2.0 chat-family ids registered (lite/pro/mini/code).
    assert {
        "doubao-seed-2-0-pro-260215",
        "doubao-seed-2-0-lite-260215",
        "doubao-seed-2-0-mini-260215",
        "doubao-seed-2-0-code-preview-260215",
    }.issubset(ids)


@pytest.mark.parametrize("scraper_cls", [DeepSeekScraper, DoubaoScraper])
def test_new_provider_models_have_no_phantom_pricing(scraper_cls):
    """Empty scraper-side pricing — main.py's litellm overlay (for deepseek)
    or PRICING_FALLBACK (for doubao) fills it. If we accidentally pre-filled
    a value here, the merge would write a stale price."""
    block = scraper_cls().build_provider_data()
    for m in block["models"]:
        p = m["pricing"]
        for k in (
            "input_per_1m_tokens", "output_per_1m_tokens",
            "input_per_1m_tokens_above_200k",
            "cache_read_per_1m_tokens", "cache_write_per_1m_tokens",
        ):
            assert p.get(k) is None, f"{m['model_id']} leaked stale {k}={p[k]!r}"
