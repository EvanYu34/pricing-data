"""Shared test fixtures."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Make repo root importable for `scrapers`, `utils`, `scripts`.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def litellm_mini() -> dict:
    """Load the litellm mini fixture (chat + ft + non-chat + dedup cases)."""
    return json.loads((FIXTURES_DIR / "litellm_mini.json").read_text(encoding="utf-8"))
