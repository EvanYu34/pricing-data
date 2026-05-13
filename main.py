#!/usr/bin/env python3
# main.py
#
# Entry point for the AI pricing data scraper (v5 — M6 rebuild).
#
# Usage:
#   python main.py                       # Run all scrapers + litellm fetch + audit
#   python main.py --provider claude     # Run only Claude scraper (still pulls litellm)
#
# Env vars:
#   USE_PLAYWRIGHT=1     enable headless fetch (auto-on in GitHub Actions)
#   FORCE_COMMIT=true    override audit failure and persist pricing.json anyway
#   DRY_RUN=true         run audit but don't write pricing.json (used by drift_check)

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from scrapers import ClaudeScraper, GeminiScraper, OpenAIScraper
from scrapers.litellm_source import fetch_litellm_prices, _canonicalize
from scripts import audit_pricing
from utils import JsonMerger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("main")

REPO_ROOT = Path(__file__).parent
PRICING_JSON = REPO_ROOT / "pricing.json"
COMMIT_MSG_FILE = REPO_ROOT / ".commit_message"

SCRAPERS: Dict[str, Any] = {
    "claude": ClaudeScraper,
    "gemini": GeminiScraper,
    "openai": OpenAIScraper,
}


def load_existing() -> Dict[str, Any]:
    if not PRICING_JSON.exists():
        return {}
    try:
        with PRICING_JSON.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not load existing pricing.json: %s", exc)
        return {}


def save_pricing(data: Dict[str, Any]) -> None:
    with PRICING_JSON.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    logger.info("Saved pricing.json (%d bytes)", PRICING_JSON.stat().st_size)


def write_commit_message(msg: str) -> None:
    COMMIT_MSG_FILE.write_text(msg, encoding="utf-8")
    logger.info("Commit message: %s", msg)


def build_commit_message(
    failed: List[str],
    diff: Dict[str, Any],
    date_str: str,
    audit_failed: bool = False,
) -> str:
    prefix = "chore: update pricing data"
    if audit_failed:
        prefix = "chore: update pricing data (FORCE-COMMIT bypassing audit)"

    if failed:
        return f"{prefix} {date_str} ({', '.join(failed)} failed)"

    parts: List[str] = []
    added_total = sum(len(v) for v in diff["added_models"].values())
    changed_total = sum(len(v) for v in diff["changed_prices"].values())
    if added_total:
        parts.append(f"+{added_total} models")
    if changed_total:
        parts.append(f"{changed_total} price changes")
    if parts:
        return f"{prefix} {date_str} ({', '.join(parts)})"
    return f"{prefix} {date_str} (all sources ok)"


def _overlay_litellm_prices(
    provider_data: Dict[str, Any],
    litellm_for_provider: Dict[str, Dict[str, Any]],
) -> int:
    """Overlay litellm pricing onto a provider_data block (in-place).

    For each model, look up the canonicalized model_id in litellm's parsed
    catalog; if found, replace the model's `pricing` dict with litellm's values
    (preserving existing notes if any) and set source="litellm".

    Returns the count of models updated.
    """
    if not litellm_for_provider:
        return 0
    count = 0
    for model in provider_data.get("models", []):
        model_id = model.get("model_id")
        if not model_id:
            continue
        canonical = _canonicalize(model_id)
        litellm_pricing = litellm_for_provider.get(canonical) or litellm_for_provider.get(model_id)
        if not litellm_pricing:
            continue
        # Preserve a couple of fields from the scraper-derived pricing if any.
        existing_notes = (model.get("pricing") or {}).get("notes") or ""
        new_pricing = dict(litellm_pricing)
        if existing_notes and not new_pricing.get("notes"):
            new_pricing["notes"] = existing_notes
        # Strip internal fields that shouldn't leak into pricing.json.
        new_pricing.pop("_litellm_providers_seen", None)
        # Note: `source` and `source_detail` are top-level model fields, not under pricing.
        model["source"] = new_pricing.pop("source", "litellm")
        if "source_detail" in new_pricing:
            model["source_detail"] = new_pricing.pop("source_detail")
        model["pricing"] = new_pricing
        count += 1
    return count


def run(providers: List[str]) -> int:
    """Main orchestration flow (plan v5 §5)."""
    existing_data = load_existing()
    new_results: Dict[str, Any] = {}
    failed_providers: List[str] = []

    # ----- Step 1: litellm fetch (cheap, ~2-5s) -----
    logger.info("--- Fetching litellm pricing catalog ---")
    litellm_data, litellm_counters = fetch_litellm_prices()
    if litellm_counters.get("fetch_succeeded"):
        logger.info(
            "litellm: kept=%d (claude=%d openai=%d gemini=%d) in %.2fs",
            litellm_counters["kept"],
            litellm_counters["by_provider"]["claude"],
            litellm_counters["by_provider"]["openai"],
            litellm_counters["by_provider"]["gemini"],
            litellm_counters["fetch_latency_s"],
        )
    else:
        logger.warning("litellm fetch failed; proceeding with scrapers only")

    # ----- Step 2: per-provider scrapers (slow, ~30s each) -----
    scraper_counters: Dict[str, Dict[str, Any]] = {}
    for name in providers:
        scraper_cls = SCRAPERS[name]
        logger.info("--- Scraping %s ---", name.upper())
        t0 = time.time()
        try:
            scraper = scraper_cls()
            provider_data = scraper.build_provider_data()
        except Exception as exc:
            logger.error("Unexpected error running %s scraper: %s", name, exc, exc_info=True)
            provider_data = {
                "fetch_status": "failed",
                "error_message": f"Unhandled exception: {exc}",
                "provider_info": {},
                "models": [],
            }

        latency = time.time() - t0
        # Step 3: overlay litellm prices onto this provider's models.
        overlay_count = _overlay_litellm_prices(
            provider_data, litellm_data.get(name, {})
        )
        logger.info(
            "%s: %d models scraped, %d enriched from litellm (%.1fs)",
            name, len(provider_data.get("models", [])), overlay_count, latency,
        )

        scraper_counters[name] = {
            "status": "OK" if provider_data.get("fetch_status") == "success" else "FAIL",
            "latency_s": round(latency, 1),
            "note": f"models={len(provider_data.get('models', []))}, "
                    f"litellm_enriched={overlay_count}",
        }

        new_results[name] = provider_data
        if provider_data["fetch_status"] != "success" or not provider_data.get("models"):
            failed_providers.append(name)

    # ----- Step 4: field-level merge with old pricing.json -----
    merger = JsonMerger()
    merged_data = merger.merge(existing_data, new_results)
    diff = merger.diff_summary(existing_data, merged_data)

    # ----- Step 5: write pricing.json to disk first so audit reads the fresh data,
    # then run audit. We'll revert the file if audit fails + no force_commit + no dry_run.
    pre_audit_existing = PRICING_JSON.read_bytes() if PRICING_JSON.exists() else None
    save_pricing(merged_data)

    # ----- Step 6: audit -----
    audit_exit = audit_pricing.run(
        litellm_counters=litellm_counters,
        scraper_counters=scraper_counters,
    )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    commit_msg = build_commit_message(
        failed_providers, diff, today, audit_failed=(audit_exit != 0)
    )
    write_commit_message(commit_msg)

    # ----- Step 7: gated persist -----
    force_commit = os.environ.get("FORCE_COMMIT", "").lower() == "true"
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"

    if dry_run:
        # drift_check path — never persist; revert what we wrote
        if pre_audit_existing is not None:
            PRICING_JSON.write_bytes(pre_audit_existing)
        else:
            PRICING_JSON.unlink(missing_ok=True)
        logger.info("DRY_RUN mode — pricing.json restored; audit_exit=%d", audit_exit)
        # In dry_run, exit non-zero only if litellm fetch failed AND coverage is low
        return audit_exit if not litellm_counters.get("fetch_succeeded") else 0

    if audit_exit != 0 and not force_commit:
        # Revert pricing.json since audit failed and we're not forcing
        if pre_audit_existing is not None:
            PRICING_JSON.write_bytes(pre_audit_existing)
            logger.error(
                "AUDIT FAILED (exit=%d). Reverted pricing.json. "
                "Run with FORCE_COMMIT=true to override.",
                audit_exit,
            )
        else:
            logger.error("AUDIT FAILED (exit=%d) and no prior pricing.json to revert to.", audit_exit)
        return audit_exit

    if audit_exit != 0 and force_commit:
        logger.warning(
            "AUDIT FAILED (exit=%d) but FORCE_COMMIT=true — persisting anyway.",
            audit_exit,
        )

    # ----- Step 8: summary -----
    logger.info("=== Summary ===")
    for name in providers:
        status = new_results[name]["fetch_status"]
        count = len(new_results[name].get("models", []))
        logger.info("  %-10s  status=%-8s  models=%d", name, status, count)
    if diff["added_models"]:
        for prov, ids in diff["added_models"].items():
            logger.info("  New models in %s: %s", prov, ", ".join(ids))
    if diff["changed_prices"]:
        for prov, ids in diff["changed_prices"].items():
            logger.info("  Price changes in %s: %s", prov, ", ".join(ids))

    return 1 if failed_providers else 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape AI platform pricing and model data into pricing.json"
    )
    parser.add_argument(
        "--provider",
        choices=list(SCRAPERS.keys()),
        default=None,
        help="Run only this provider's scraper (default: all)",
    )
    args = parser.parse_args()

    providers = [args.provider] if args.provider else list(SCRAPERS.keys())
    exit_code = run(providers)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
