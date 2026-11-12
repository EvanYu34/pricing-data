"""litellm 的 deprecation_date → pricing.json 的 is_deprecated (2026-11-12)。

只认优先级最高的来源 (官方 API) 写的日期; 提前 DEPRECATION_LEAD_DAYS 天标; 只标 True。
"""
from __future__ import annotations

from datetime import datetime, timezone

import main
from scrapers import litellm_source


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._p


def _chat(provider, price=1e-6, dep=None):
    e = {"mode": "chat", "litellm_provider": provider,
         "input_cost_per_token": price, "output_cost_per_token": price * 4}
    if dep:
        e["deprecation_date"] = dep
    return e


LITELLM = {
    # Gemini API 写了 12-01, Vertex 更早 → 用 Gemini API 的
    "gemini/gemini-2.5-pro": _chat("gemini", dep="2026-12-01"),
    "gemini-2.5-pro": _chat("vertex_ai-language-models", dep="2026-09-01"),
    # Gemini API 没写, 只有 Vertex 写了 → 不算下线
    "gemini/gemini-2.5-flash-lite": _chat("gemini"),
    "gemini-2.5-flash-lite": _chat("vertex_ai-language-models", dep="2026-10-20"),
    # 只有 Vertex 这一个来源时就用它的
    "gemini-old-vertex-only-pro": _chat("vertex_ai-language-models", dep="2026-01-01"),
    "gemini/gemini-3.8-flash": _chat("gemini"),
    "gemini/gemini-bad-date-pro": _chat("gemini", dep="soon"),
}


def _fetch(monkeypatch):
    monkeypatch.setattr(litellm_source.requests, "get", lambda *a, **k: _Resp(LITELLM))
    data, _ = litellm_source.fetch_litellm_prices()
    return data


def test_deprecation_date_from_highest_priority_source(monkeypatch):
    g = _fetch(monkeypatch)["gemini"]
    assert g["gemini-2.5-pro"]["_deprecation_date"] == "2026-12-01"
    assert "_deprecation_date" not in g["gemini-2.5-flash-lite"]
    assert g["gemini-old-vertex-only-pro"]["_deprecation_date"] == "2026-01-01"
    assert "_deprecation_date" not in g["gemini-3.8-flash"]
    assert "_deprecation_date" not in g["gemini-bad-date-pro"]


def _merged():
    ids = ["gemini-2.5-pro", "gemini-2.5-flash-lite", "gemini-3.8-flash", "gemini-old-vertex-only-pro"]
    return {"sources": {"gemini": {"models": [{"model_id": i, "is_deprecated": False} for i in ids]}}}


def _flags(merged):
    return {m["model_id"]: m["is_deprecated"] for m in merged["sources"]["gemini"]["models"]}


def test_flags_models_two_weeks_before_shutdown(monkeypatch):
    data = _fetch(monkeypatch)
    m = _merged()
    early = datetime(2026, 11, 12, tzinfo=timezone.utc)      # 12-01 还有 19 天
    assert main._apply_litellm_deprecations(m, data, early) == ["gemini/gemini-old-vertex-only-pro"]
    m = _merged()
    near = datetime(2026, 11, 23, tzinfo=timezone.utc)       # 还有 8 天 (< 14) → 标上
    main._apply_litellm_deprecations(m, data, near)
    assert _flags(m) == {"gemini-2.5-pro": True, "gemini-2.5-flash-lite": False,
                         "gemini-3.8-flash": False, "gemini-old-vertex-only-pro": True}


def test_never_unflags_and_internal_field_not_written(monkeypatch):
    data = _fetch(monkeypatch)
    m = _merged()
    m["sources"]["gemini"]["models"][2]["is_deprecated"] = True   # 别处标的下线, 不改回去
    main._apply_litellm_deprecations(m, data, datetime(2026, 11, 12, tzinfo=timezone.utc))
    assert _flags(m)["gemini-3.8-flash"] is True

    block = {"models": [{"model_id": "gemini-2.5-pro", "pricing": {}}]}
    main._overlay_litellm_prices(block, data["gemini"])
    assert "_deprecation_date" not in block["models"][0]["pricing"]
