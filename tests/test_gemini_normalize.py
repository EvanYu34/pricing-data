"""Regression tests for the gemini scraper's _normalize_model_id.

Filed under pricing-data#5: gemini coverage was ~16% because the scraper
emitted IDs like "gemini 2.5 flash" (with spaces) and "gemini 3 pro
previewshut down" that didn't match the canonical form used by litellm,
so the merge step left them with null pricing.

Tests pin:
  1. The newly-added 2.5 family entries in _DISPLAY_TO_ID.
  2. The generic "gemini X.Y variant" → "gemini-X.Y-variant" fallback
     that catches future versions before they're hand-mapped.
  3. Pre-existing IDs (already-canonical strings, embedding family) still
     round-trip cleanly.
"""
import pytest

from scrapers.gemini_scraper import _normalize_model_id


@pytest.mark.parametrize("display,expected", [
    # Explicit table entries — the 2.5 family that pricing-data#5
    # surfaced as broken.
    ("gemini 2.5 flash", "gemini-2.5-flash"),
    ("Gemini 2.5 Flash", "gemini-2.5-flash"),         # case-insensitive
    ("gemini 2.5 pro", "gemini-2.5-pro"),
    ("gemini 2.5 flash-lite", "gemini-2.5-flash-lite"),
    # 2.0 family still works
    ("gemini 2.0 flash", "gemini-2.0-flash"),
    ("gemini 2.0 flash lite", "gemini-2.0-flash-lite"),
    # 1.5 family still works
    ("gemini 1.5 pro", "gemini-1.5-pro"),
    ("gemini 1.5 flash-8b", "gemini-1.5-flash-8b"),
    # Generic fallback for unmapped future versions
    ("gemini 3 pro", "gemini-3-pro"),
    ("gemini 3 flash", "gemini-3-flash"),
    ("gemini 3.1 flash live", "gemini-3.1-flash-live"),
    ("gemini 3.1 flash-lite", "gemini-3.1-flash-lite"),
    # Already-canonical IDs round-trip
    ("gemini-1.5-pro", "gemini-1.5-pro"),
    ("gemini-2.0-flash-exp", "gemini-2.0-flash-exp"),
    # Embedding family
    ("text embedding", "text-embedding-004"),
    ("text-embedding-004", "text-embedding-004"),
    # Imagen
    ("imagen 3", "imagen-3.0-generate-001"),
])
def test_gemini_normalize_canonical(display, expected):
    assert _normalize_model_id(display) == expected


def test_garbage_text_after_gemini_keyword_gets_normalised():
    """Real bad string we saw in pricing.json: "gemini 3 pro previewshut
    down" — joined two words without a space due to a scraper text-glue
    bug. The generic fallback still produces a usable hyphenated ID so
    downstream merge can at least pick up the row."""
    out = _normalize_model_id("gemini 3 pro previewshut down")
    # We don't care about the exact junk-tail handling, just that the
    # output is non-empty, hyphenated, gemini-prefixed, and lowercase.
    assert out.startswith("gemini-")
    assert " " not in out
    assert out == out.lower()


def test_unrelated_text_passes_through_untouched():
    """Don't accidentally normalise non-gemini strings to a "gemini-..." ID."""
    assert _normalize_model_id("random text") == "random text"
    assert _normalize_model_id("OpenAI gpt-4") == "openai gpt-4"
