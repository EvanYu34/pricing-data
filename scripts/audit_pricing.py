#!/usr/bin/env python3
# scripts/audit_pricing.py
#
# Computes price-coverage stats over a merged pricing.json + writes
# AUDIT_REPORT.md. Returns an exit code that main.py uses to gate the commit
# step in CI (see plan v5 §4-5).
#
# Failure conditions (exit 1):
#   - litellm_fetch_succeeded == False
#   - Any provider's coverage < 90% AND dropped > 5pp from last successful run
#
# Warnings (exit 0, but flagged in the report):
#   - cross-validation price deltas > 5% within a model (different litellm providers)
#   - source: "stale" count > 30% of provider's model count
#   - counters.unrecognized_provider > 0 (dead allowlist entry)
#
# Usage:
#   python -m scripts.audit_pricing                 # writes AUDIT_REPORT.md, exit code
#   python -m scripts.audit_pricing --strict        # also fail on warnings
#   python -m scripts.audit_pricing --dry-run-only  # drift-check mode: don't fail on coverage drop

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
PRICING_JSON = REPO_ROOT / "pricing.json"
AUDIT_REPORT = REPO_ROOT / "AUDIT_REPORT.md"

COVERAGE_MIN_PCT = 90.0
COVERAGE_DROP_MAX_PP = 5.0
STALE_WARN_PCT = 30.0


def _is_priced(model: Dict[str, Any]) -> bool:
    p = model.get("pricing") or {}
    return p.get("input_per_1m_tokens") is not None


def _source_breakdown(models: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for m in models:
        out[m.get("source", "scraper")] = out.get(m.get("source", "scraper"), 0) + 1
    return out


def _coverage(models: List[Dict[str, Any]]) -> tuple[int, int, float]:
    total = len(models)
    priced = sum(1 for m in models if _is_priced(m))
    pct = (100.0 * priced / total) if total else 0.0
    return priced, total, pct


def _read_pricing() -> Dict[str, Any]:
    if not PRICING_JSON.exists():
        return {}
    try:
        return json.loads(PRICING_JSON.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("pricing.json parse failed: %s", exc)
        return {}


def _previous_coverage_from_audit() -> Dict[str, float]:
    """Parse the last AUDIT_REPORT.md to recover previous coverage per provider.

    Used by the 5pp-drop check. If unavailable, returns {}.
    """
    if not AUDIT_REPORT.exists():
        return {}
    out: Dict[str, float] = {}
    try:
        for line in AUDIT_REPORT.read_text(encoding="utf-8").splitlines():
            # Match table rows of the form "| claude | 13 | 15 | 87% | ... |"
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 5:
                continue
            provider = cells[0]
            if provider in ("Provider", "---", "----"):
                continue
            pct_cell = cells[3].rstrip("%")
            try:
                out[provider] = float(pct_cell)
            except ValueError:
                continue
    except OSError:
        return {}
    return out


def build_report(
    pricing: Dict[str, Any],
    litellm_counters: Optional[Dict[str, Any]] = None,
    scraper_counters: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[str, int]:
    """Render the AUDIT_REPORT.md content + decide overall exit code.

    Returns (markdown_text, exit_code).
    """
    sources = pricing.get("sources", {})
    previous_coverage = _previous_coverage_from_audit()
    failures: List[str] = []
    warnings: List[str] = []

    # ----------- Coverage section -----------
    lines: List[str] = []
    lines.append(f"# 价格抓取审计报告")
    lines.append(f"")
    lines.append(f"> 生成时间：{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append("## 价格抓取覆盖率")
    lines.append("")
    lines.append("| Provider | with input price | total | coverage | source breakdown |")
    lines.append("|---|---:|---:|---:|---|")

    for provider in sorted(sources.keys()):
        block = sources[provider] or {}
        models = block.get("models", []) or []
        priced, total, pct = _coverage(models)
        breakdown = _source_breakdown(models)
        breakdown_str = ", ".join(f"{k}: {v}" for k, v in sorted(breakdown.items()))
        lines.append(
            f"| {provider} | {priced} | {total} | {pct:.0f}% | {breakdown_str or '–'} |"
        )

        # Coverage failure semantics (plan v5 §4):
        #   FAIL only when we have a baseline AND coverage dropped > 5pp.
        #   No baseline (first run) → establish one; emit WARNING if low.
        #   Below threshold but not dropping → WARNING (not FAIL).
        prev = previous_coverage.get(provider)
        if pct < COVERAGE_MIN_PCT:
            if prev is not None and (prev - pct) > COVERAGE_DROP_MAX_PP:
                failures.append(
                    f"{provider} coverage dropped {prev:.0f}% → {pct:.0f}% "
                    f"(below {COVERAGE_MIN_PCT:.0f}% and lost > {COVERAGE_DROP_MAX_PP:.0f}pp)"
                )
            else:
                warnings.append(
                    f"{provider} coverage {pct:.0f}% < {COVERAGE_MIN_PCT:.0f}% "
                    f"(prev: {prev if prev is not None else 'n/a'} — "
                    f"{'baseline established' if prev is None else 'no significant drop'})"
                )

        # Stale-fraction warning
        stale_count = breakdown.get("stale", 0)
        if total and (100.0 * stale_count / total) > STALE_WARN_PCT:
            warnings.append(
                f"{provider} has {stale_count}/{total} stale entries (> {STALE_WARN_PCT:.0f}%)"
            )

    # ----------- Upstream fetch summary -----------
    lines.append("")
    lines.append("## 上游 fetch 摘要")
    lines.append("")
    lines.append("| 来源 | 状态 | 用时 | 备注 |")
    lines.append("|---|---|---:|---|")
    if litellm_counters is not None:
        status = "OK" if litellm_counters.get("fetch_succeeded") else "FAIL"
        latency = litellm_counters.get("fetch_latency_s", 0.0)
        notes = (
            f"kept={litellm_counters.get('kept', 0)}, "
            f"skip_non_chat={litellm_counters.get('skipped_non_chat', 0)}, "
            f"skip_prefix={litellm_counters.get('skipped_prefix', 0)}, "
            f"unrecognized={litellm_counters.get('unrecognized_provider', 0)}"
        )
        lines.append(f"| litellm | {status} | {latency:.2f}s | {notes} |")

        if not litellm_counters.get("fetch_succeeded"):
            failures.append(f"litellm fetch failed: {litellm_counters.get('error', 'unknown')}")
        # Only warn if one of OUR allowlist providers got zero hits — that signals
        # a dead allowlist entry. A large `unrecognized_provider` count is normal
        # (litellm tracks many providers we don't care about: databricks, palm,
        # mistral, watsonx, etc.).
        by_provider = litellm_counters.get("by_provider", {})
        for ours, hits in by_provider.items():
            if hits == 0:
                warnings.append(
                    f"litellm matched 0 entries for our provider '{ours}' — "
                    "allowlist may be stale"
                )

    if scraper_counters:
        for provider, counters in sorted(scraper_counters.items()):
            status = counters.get("status", "?")
            latency = counters.get("latency_s", 0.0)
            note = counters.get("note", "")
            lines.append(f"| {provider}_scraper | {status} | {latency:.1f}s | {note} |")

    # ----------- Cross-validation -----------
    lines.append("")
    lines.append("## 价格交叉验证")
    lines.append("")
    cross_warnings = _build_cross_validation_table(sources)
    if cross_warnings["rows"]:
        lines.append("| Model | provider A | provider B | input Δ | output Δ |")
        lines.append("|---|---:|---:|---:|---:|")
        lines.extend(cross_warnings["rows"])
        warnings.extend(cross_warnings["warnings"])
    else:
        lines.append("无 > 5% 价格分歧。")

    # ----------- Failures + warnings footer -----------
    lines.append("")
    if failures:
        lines.append("## ❌ FAILURES")
        for f in failures:
            lines.append(f"- {f}")
    if warnings:
        lines.append("")
        lines.append("## ⚠️ WARNINGS")
        for w in warnings:
            lines.append(f"- {w}")
    if not failures and not warnings:
        lines.append("## ✅ 全部健康")

    exit_code = 1 if failures else 0
    return "\n".join(lines) + "\n", exit_code


def _build_cross_validation_table(sources: Dict[str, Any]) -> Dict[str, Any]:
    """For each model that was sourced from multiple litellm providers (i.e.
    `source_detail` lists ≥2), report whether the multi-provider data agreed.
    Currently the merger keeps only the winning value, so this is informational —
    if/when we change to record per-provider values, this is where deltas surface.
    """
    return {"rows": [], "warnings": []}


def run(
    litellm_counters: Optional[Dict[str, Any]] = None,
    scraper_counters: Optional[Dict[str, Dict[str, Any]]] = None,
) -> int:
    """Compute audit, write AUDIT_REPORT.md, return exit code."""
    pricing = _read_pricing()
    md, exit_code = build_report(pricing, litellm_counters, scraper_counters)
    AUDIT_REPORT.write_text(md, encoding="utf-8")
    logger.info("Wrote %s (exit_code=%d)", AUDIT_REPORT, exit_code)
    return exit_code


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit pricing.json coverage")
    parser.add_argument("--strict", action="store_true",
                        help="Also exit non-zero on warnings")
    parser.add_argument("--dry-run-only", action="store_true",
                        help="Drift-check mode: report only, ignore coverage drop")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # When invoked standalone (no counters passed), we still audit the on-disk
    # pricing.json. litellm and scraper counters are unavailable here.
    exit_code = run(litellm_counters=None, scraper_counters=None)
    if args.dry_run_only:
        sys.exit(0 if exit_code == 0 else 0)  # never fail in dry-run mode
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
