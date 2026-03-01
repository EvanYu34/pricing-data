#!/usr/bin/env python3
# main.py
#
# Entry point for the AI pricing data scraper.
#
# Usage:
#   python main.py                 # Run all scrapers
#   python main.py --provider claude   # Run only Claude scraper
#   USE_PLAYWRIGHT=1 python main.py    # Enable Playwright (local dev)
#
# In GitHub Actions, Playwright is auto-enabled via the GITHUB_ACTIONS env var.

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from scrapers import ClaudeScraper, GeminiScraper, OpenAIScraper
from utils import JsonMerger

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("main")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent
PRICING_JSON = REPO_ROOT / "pricing.json"
COMMIT_MSG_FILE = REPO_ROOT / ".commit_message"

# ---------------------------------------------------------------------------
# Scraper registry
# ---------------------------------------------------------------------------
SCRAPERS: Dict[str, Any] = {
    "claude": ClaudeScraper,
    "gemini": GeminiScraper,
    "openai": OpenAIScraper,
}


def load_existing() -> Dict[str, Any]:
    """Load current pricing.json; return empty dict if file absent or corrupt."""
    if not PRICING_JSON.exists():
        logger.info("pricing.json not found; starting fresh")
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
        fh.write("\n")  # trailing newline for cleaner git diffs
    logger.info("Saved pricing.json (%d bytes)", PRICING_JSON.stat().st_size)


def write_commit_message(msg: str) -> None:
    COMMIT_MSG_FILE.write_text(msg, encoding="utf-8")
    logger.info("Commit message: %s", msg)


def build_commit_message(
    failed: List[str],
    diff: Dict[str, Any],
    date_str: str,
) -> str:
    if failed:
        failed_str = ", ".join(failed)
        return f"chore: update pricing data {date_str} ({failed_str} failed)"

    parts: List[str] = []
    added_total = sum(len(v) for v in diff["added_models"].values())
    changed_total = sum(len(v) for v in diff["changed_prices"].values())

    if added_total:
        parts.append(f"+{added_total} models")
    if changed_total:
        parts.append(f"{changed_total} price changes")

    if parts:
        detail = ", ".join(parts)
        return f"chore: update pricing data {date_str} ({detail})"
    return f"chore: update pricing data {date_str} (all sources ok)"


def run(providers: List[str]) -> int:
    """
    Run the specified scrapers, merge results, write pricing.json, and
    write a .commit_message file.

    Returns exit code: 0 = all succeeded, 1 = at least one provider failed.
    """
    existing_data = load_existing()
    new_results: Dict[str, Any] = {}
    failed_providers: List[str] = []

    for name in providers:
        scraper_cls = SCRAPERS[name]
        logger.info("--- Scraping %s ---", name.upper())
        try:
            scraper = scraper_cls()
            provider_data = scraper.build_provider_data()
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error running %s scraper: %s", name, exc, exc_info=True)
            provider_data = {
                "fetch_status": "failed",
                "error_message": f"Unhandled exception: {exc}",
                "provider_info": {},
                "models": [],
            }

        new_results[name] = provider_data
        if provider_data["fetch_status"] != "success" or not provider_data.get("models"):
            failed_providers.append(name)
            logger.warning(
                "%s: FAILED — %s",
                name,
                provider_data.get("error_message", "no models returned"),
            )
        else:
            logger.info("%s: OK — %d models", name, len(provider_data["models"]))

    # Merge new data with existing
    merger = JsonMerger()
    merged_data = merger.merge(existing_data, new_results)

    # Compute diff for the commit message
    diff = merger.diff_summary(existing_data, merged_data)

    # Persist
    save_pricing(merged_data)

    # Write commit message
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    commit_msg = build_commit_message(failed_providers, diff, today)
    write_commit_message(commit_msg)

    # Print summary
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
