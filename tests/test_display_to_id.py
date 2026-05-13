"""Regression test for the _DISPLAY_TO_ID substring-ordering bug.

Pre-v5, `_normalize_model_id("Claude Opus 4.5")` returned `claude-opus-4-6`
because the first matching substring in the dict was `"claude opus 4"`.
v5 sorts entries longest-first.
"""
import pytest

from scrapers.claude_scraper import _normalize_model_id


@pytest.mark.parametrize("display,expected", [
    ("Claude Opus 4.5", "claude-opus-4-5"),
    ("Claude Sonnet 4.5", "claude-sonnet-4-5"),
    ("Claude Opus 4.6", "claude-opus-4-6"),
    ("Claude Sonnet 4.6", "claude-sonnet-4-6"),
    ("Claude Haiku 4.5", "claude-haiku-4-5"),
    ("Claude 3.5 Sonnet", "claude-3-5-sonnet-20241022"),
    ("claude 3 opus", "claude-3-opus-20240229"),
])
def test_display_to_id_canonical_mapping(display, expected):
    assert _normalize_model_id(display) == expected
