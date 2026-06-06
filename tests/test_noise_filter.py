"""Unit tests for utils.noise_filter."""
from __future__ import annotations

import pytest

from utils.noise_filter import is_noise_model_id, filter_provider_models


@pytest.mark.parametrize("model_id,is_noise", [
    # Real chat models — keep
    ("claude-sonnet-4-5", False),
    ("claude-opus-4-7", False),
    ("gpt-4o", False),
    ("gpt-4o-mini", False),
    ("gpt-4.1-mini", False),
    ("o1", False),               # short but real reasoning model
    ("o3", False),               # short but real reasoning model
    ("o4-mini", False),
    ("o3-mini", False),
    ("o1-preview", False),
    ("gpt-4o-audio-preview", False),  # multimodal chat with audio inputs — keep
    ("gemini-2.5-pro", False),
    ("gemini-2.0-flash", False),
    ("claude-3-5-sonnet-20241022", False),

    # Speech / transcription — drop
    ("tts-1", True),
    ("tts-1-hd", True),
    ("whisper-1", True),
    ("gpt-4o-transcribe", True),
    ("gpt-4o-transcribe-diarize", True),

    # Image generation — drop
    ("dall-e-2", True),
    ("dall-e-3", True),
    ("gpt-image-1", True),
    ("gpt-image-1-mini", True),
    ("imagen-3.0-generate-001", True),
    ("imagen 4", True),

    # Embeddings — drop
    ("text-embedding-3-large", True),
    ("text-embedding-3-small", True),
    ("text-embedding-ada-002", True),
    ("embedding-001", True),
    ("gemini embeddings", True),
    ("gemini embedding", True),
    ("gemini embedding 2", True),

    # Moderation / realtime / robotics / deep-research — not chat
    ("omni-moderation-latest", True),
    ("gpt-realtime", True),
    ("gpt-realtime-mini", True),
    ("gemini robotics-er 1.6preview", True),
    ("o3-deep-research", True),
    ("o4-mini-deep-research", True),

    # Vague tier labels — drop
    ("standard", True),
    ("priority", True),
    ("flex", True),
    ("batch", True),
    ("pricing for tools", True),
    ("ga", True),

    # OCR junk — letter-digit-letter without separator (regex pattern)
    ("o51u", True),
    ("o6f", True),

    # Non-ASCII garbage
    ("gpt-とても", True),

    # All-digit / pure-numeric — not a model id
    ("3.5", True),
    ("1.5.0", True),

    # Whitespace = scraper tokenization bug (#5)
    ("gemini 2.5 flash", True),
    ("gemini 3 pro", True),
    ("gemini 2.5 flash-lite", True),
    # Scraper-concat bugs (#5)
    ("gemini-3-pro-previewshut-down", True),
    ("gemini-3.1-flash-livepreview", True),
    # OpenAI scraper junk added to TIER_ALIASES (#5)
    ("gpt-audio", True),
    ("gpt-audio-1.5", True),
    ("gpt-audio-mini", True),
    ("gpt-image-latest", True),
    ("gpt-oss", True),
    ("gpt-oss-120b", True),
    ("gpt-oss-20b", True),
    ("gpt-5-codex", True),
    ("gpt-5.1-codex-max", True),
    # ...but real chat models adjacent stay
    ("gpt-4o-audio-preview", False),    # has "audio" in name but is real chat-with-audio
    ("gemini-2.5-pro", False),          # has digits but valid model_id
])
def test_is_noise_model_id(model_id, is_noise):
    assert is_noise_model_id(model_id) is is_noise, f"{model_id!r} should be noise={is_noise}"


def test_filter_provider_models_in_place():
    data = {
        "models": [
            {"model_id": "claude-sonnet-4-5"},
            {"model_id": "tts-1"},
            {"model_id": "whisper-1"},
            {"model_id": "claude-opus-4-5"},
            {"model_id": "standard"},
            {"model_id": "gpt-4o"},
            {"model_id": "o1"},        # real short id — keep
            {"model_id": "o51u"},      # OCR junk — drop
        ],
    }
    dropped = filter_provider_models(data)
    assert dropped == 4  # tts-1, whisper-1, standard, o51u
    assert {m["model_id"] for m in data["models"]} == {
        "claude-sonnet-4-5", "claude-opus-4-5", "gpt-4o", "o1",
    }


def test_filter_handles_empty_input():
    data = {"models": []}
    assert filter_provider_models(data) == 0
    assert data["models"] == []

    data = {}
    assert filter_provider_models(data) == 0


def test_filter_handles_malformed_entries():
    data = {
        "models": [
            {"model_id": "claude-sonnet-4-5"},
            "not-a-dict",            # should be dropped
            {"no_id_field": "x"},    # should be dropped
            {"model_id": None},      # should be dropped
        ],
    }
    filter_provider_models(data)
    assert data["models"] == [{"model_id": "claude-sonnet-4-5"}]
