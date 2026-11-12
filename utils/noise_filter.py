"""Drop non-chat model_ids that pollute the catalog.

The scrapers' auto-discovery regexes match any token that looks like a model
id, so they pull in things like `tts-1`, `whisper-1`, `dall-e-3`,
`text-embedding-3-large`, vague tier labels (`standard`, `priority`, `flex`),
and OCR junk from JS bundles (`o51u`). These aren't chat models and shouldn't
appear in the LLM dropdown.

Applied at JsonMerger.merge() output so both fresh scrapes AND legacy
pricing.json entries get cleaned in one pass.
"""
from __future__ import annotations

# Substrings (case-insensitive) in model_id → drop. These describe the
# *capability*, not chat-model-ness.
NON_CHAT_SUBSTRINGS = (
    "embedding", "embed",
    "whisper", "transcribe", "stt",
    "tts", "text-to-speech",
    "dall-e", "dalle",
    "imagen", "image-gen", "image-1",
    "moderation",
    "realtime",
    "robotics",
    "deep-research", "deep research",
    "computer-use",
    "tokenizer",
    "gemini live", "live ",  # Gemini Live API entries (not standard chat)
)

# Vague tier aliases / category names mistakenly captured as model IDs.
# Exact-match only.
TIER_ALIASES = {
    "standard", "priority", "flex", "scale", "batch",
    "pricing for tools", "preview", "ga",
    # OpenAI scraper junk (#5): audio-only / image-only / open-weights /
    # category labels that aren't usable chat-API IDs in the dropdown.
    "gpt-audio", "gpt-audio-1.5", "gpt-audio-mini",
    "gpt-image-latest", "gpt-image",
    "gpt-oss", "gpt-oss-120b", "gpt-oss-20b",
    # codex line retired 2023; "gpt-5-codex" / "gpt-5.1-codex-max" / etc.
    # are scraper artifacts from upcoming-product blurbs, not real IDs.
    "gpt-5-codex", "gpt-5.1-codex", "gpt-5.1-codex-max",
    "gpt-5.2-codex", "gpt-5.3-codex",
    # Gemini 页面上的一个词, 被 merge 配上了一组价格 (1.0 / 2.0), 出现在 AI 选择器里
    "contributor",
}


# Substrings that flag scraper-concat bugs (whitespace stripped during
# tokenization fused two words). Distinct from NON_CHAT_SUBSTRINGS — these
# describe noise *pipeline*, not capability class.
_SCRAPER_BUG_SUBSTRINGS = (
    "previewshut-down",   # "preview shut-down" lost the space
    "livepreview",        # "live preview" lost the space
)


def _has_whitespace(model_id: str) -> bool:
    """Real model_ids are token-safe (a-z 0-9 . -). Whitespace = scraper bug."""
    return any(c.isspace() for c in model_id)

# Junk regex patterns. `o51u` / `o6f...` are OCR artifacts from JS bundles.
# Real OpenAI reasoning models (`o1`, `o3`, `o4-mini`) follow letter+digits
# only or letter+digits+hyphen-suffix. Mixed letter-digit-letter without
# hyphen separator is the giveaway.
import re as _re
_JUNK_RE = _re.compile(r"^[a-z]\d+[a-z]+$")  # matches o51u, o6f, etc.

# Gemini 抓取器从文档页 (标题 / 锚点 / 分类名) 扫出来的、不是真 API id 的形状 (2026-11):
# - gemini-25-pro / gemini-25-flash-lite: 版本号丢了点 (真 id gemini-2.5-pro)
# - gemini-3-8-flash / gemini-3-5-flash-lite: 点变成横杠 (真 id gemini-3.8-flash)
# - gemini-3 / gemini-3.6 / gemini-4: 只有系列名, 没有 flash / pro 这种档位
# - gemini-3-models / gemini-2.5-flash-models: 文档的分类标题
# 真 id 的主版本都是一位数 + 可选「.小版本」, 例如 gemini-3.1-pro-preview / gemini-4-argon。
_GEMINI_MALFORMED_RE = _re.compile(
    r"^gemini-(\d{2,}-|\d-\d+-|\d+(\.\d+)?$)|^gemini-.*-models$"
)


def _is_non_ascii(model_id: str) -> bool:
    try:
        model_id.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


def _is_all_digits_or_punct(model_id: str) -> bool:
    """e.g. `1.5`, `3.0-001` — not real model ids."""
    stripped = model_id.replace(".", "").replace("-", "").replace("_", "")
    return stripped.isdigit() if stripped else True


def is_noise_model_id(model_id: str) -> bool:
    """Return True if this model_id should be filtered out of the catalog."""
    if not isinstance(model_id, str):
        return True
    model_id = model_id.strip()
    if not model_id:
        return True
    if _is_non_ascii(model_id):
        return True
    if _is_all_digits_or_punct(model_id):
        return True
    if _JUNK_RE.match(model_id.casefold()):
        return True
    if _GEMINI_MALFORMED_RE.match(model_id.casefold()):
        return True
    # Whitespace in model_id = scraper tokenization bug (e.g. "gemini 2.5 flash").
    # Real Google / OpenAI / Anthropic API IDs only use [a-z0-9.-].
    if _has_whitespace(model_id):
        return True

    lo = model_id.casefold()
    if lo in TIER_ALIASES:
        return True
    for sub in NON_CHAT_SUBSTRINGS:
        if sub in lo:
            return True
    for sub in _SCRAPER_BUG_SUBSTRINGS:
        if sub in lo:
            return True
    return False


def filter_provider_models(provider_data: dict) -> int:
    """Drop noise models in-place from a provider_data dict. Returns count dropped."""
    models = provider_data.get("models", []) or []
    before = len(models)
    provider_data["models"] = [
        m for m in models
        if isinstance(m, dict) and not is_noise_model_id(m.get("model_id", ""))
    ]
    return before - len(provider_data["models"])
