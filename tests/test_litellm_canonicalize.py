"""Unit tests for scrapers.litellm_source._canonicalize.

Plan v5 §1 defines 7 transforms (including -latest); these tests cover each
plus combined cases and idempotency.
"""
from __future__ import annotations

import pytest

from scrapers.litellm_source import _canonicalize


@pytest.mark.parametrize("raw,expected", [
    # Bare canonical IDs unchanged
    ("claude-sonnet-4-5", "claude-sonnet-4-5"),
    ("gpt-4o", "gpt-4o"),
    ("gemini-2.5-pro", "gemini-2.5-pro"),

    # gemini/ prefix
    ("gemini/gemini-2.5-pro", "gemini-2.5-pro"),

    # vertex_ai/ prefix
    ("vertex_ai/claude-3-5-sonnet@20240620", "claude-3-5-sonnet-20240620"),

    # bedrock/ + regional + anthropic. namespace + version suffix
    ("bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0", "claude-3-5-sonnet-20241022"),
    ("us.anthropic.claude-3-5-sonnet-20241022-v2:0", "claude-3-5-sonnet-20241022"),
    ("anthropic.claude-3-5-haiku-20241022", "claude-3-5-haiku-20241022"),

    # Version suffix without colon (e.g. -v1 alone)
    ("us.anthropic.claude-opus-4-6-v1", "claude-opus-4-6"),

    # -latest alias keeps its own canonical row
    ("claude-3-5-sonnet-latest", "claude-3-5-sonnet"),

    # Multiple regional prefixes are not common but should be tolerated
    ("eu.anthropic.claude-haiku-4-5", "claude-haiku-4-5"),
    ("apac.anthropic.claude-opus-4-7", "claude-opus-4-7"),
])
def test_canonicalize_examples(raw, expected):
    assert _canonicalize(raw) == expected


def test_idempotent():
    """Applying canonicalize twice yields the same result as once."""
    samples = [
        "bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        "vertex_ai/claude-3-5-sonnet@20240620",
        "claude-3-5-sonnet-latest",
        "claude-sonnet-4-5",
    ]
    for s in samples:
        once = _canonicalize(s)
        twice = _canonicalize(once)
        assert once == twice, f"idempotency broken for {s!r}: {once!r} → {twice!r}"


def test_empty_input():
    assert _canonicalize("") == ""
