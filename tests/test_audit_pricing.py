"""Unit tests for scripts.audit_pricing report rendering + exit codes."""
from __future__ import annotations

from scripts import audit_pricing


def _pricing_skel(coverage_pct: int, provider: str = "claude", source: str = "litellm") -> dict:
    """Synthesize a pricing.json-shaped dict with the given input-price coverage."""
    n_total = 10
    n_priced = round(n_total * coverage_pct / 100)
    models = []
    for i in range(n_total):
        has_price = i < n_priced
        models.append({
            "model_id": f"{provider}-model-{i}",
            "pricing": {
                "currency": "USD",
                "input_per_1m_tokens": 1.0 if has_price else None,
                "output_per_1m_tokens": 2.0 if has_price else None,
            },
            "source": source if has_price else "fallback",
        })
    return {
        "last_updated": "2026-05-13T00:00:00Z",
        "sources": {provider: {"fetch_status": "success", "models": models}},
    }


def test_report_contains_coverage_table():
    pricing = _pricing_skel(coverage_pct=80)
    md, exit_code = audit_pricing.build_report(pricing, litellm_counters={
        "fetch_succeeded": True, "fetch_latency_s": 1.5, "kept": 100,
        "skipped_non_chat": 50, "skipped_prefix": 30, "unrecognized_provider": 0,
    })
    assert "价格抓取覆盖率" in md
    assert "claude" in md
    assert "80%" in md
    # 80% coverage: passes only when previous was at most 85% (no drop > 5pp).
    # Without a previous report on disk, the threshold IS triggered → exit 1.


def test_litellm_fetch_failure_fails():
    pricing = _pricing_skel(coverage_pct=95)
    md, exit_code = audit_pricing.build_report(pricing, litellm_counters={
        "fetch_succeeded": False, "error": "ConnectionError", "fetch_latency_s": 0.1,
    })
    assert exit_code == 1
    assert "FAIL" in md or "❌" in md


def test_full_coverage_passes(tmp_path, monkeypatch):
    """100% coverage with successful litellm fetch → exit 0."""
    monkeypatch.setattr(audit_pricing, "AUDIT_REPORT", tmp_path / "AUDIT_REPORT.md")
    pricing = _pricing_skel(coverage_pct=100)
    md, exit_code = audit_pricing.build_report(pricing, litellm_counters={
        "fetch_succeeded": True, "fetch_latency_s": 1.0, "kept": 100,
        "skipped_non_chat": 0, "skipped_prefix": 0, "unrecognized_provider": 0,
    })
    assert exit_code == 0
    assert "全部健康" in md or "FAILURES" not in md
