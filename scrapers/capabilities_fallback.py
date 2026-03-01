# scrapers/capabilities_fallback.py
#
# Human-maintained fallback configuration.
# Used when live page parsing fails or returns empty capability lists.
# Update this file whenever new models are released or capabilities change.
# TODO: Keep this file in sync with official model documentation.

# ---------------------------------------------------------------------------
# Capability lists per model
# ---------------------------------------------------------------------------

CAPABILITIES_FALLBACK = {
    # -----------------------------------------------------------------------
    # Anthropic / Claude
    # -----------------------------------------------------------------------
    "claude": {
        # Claude 4.x series (TODO: verify exact IDs when officially announced)
        "claude-opus-4-6": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "claude-sonnet-4-6": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "claude-opus-4-5": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "claude-sonnet-4-5": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "claude-haiku-4-5": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        # Claude 3.7 series
        "claude-3-7-sonnet-20250219": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        # Claude 3.5 series
        "claude-3-5-sonnet-20241022": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "claude-3-5-sonnet-20240620": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "claude-3-5-haiku-20241022": [
            "text_generation",
            "translation",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        # Claude 3 series
        "claude-3-opus-20240229": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "claude-3-sonnet-20240229": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "claude-3-haiku-20240307": [
            "text_generation",
            "translation",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
    },

    # -----------------------------------------------------------------------
    # Google / Gemini
    # -----------------------------------------------------------------------
    "gemini": {
        # Gemini 2.x series
        "gemini-2.0-flash": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gemini-2.0-flash-lite": [
            "text_generation",
            "translation",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gemini-2.0-flash-thinking-exp": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gemini-2.0-flash-exp": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gemini-2.0-pro-exp": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        # Gemini 1.5 series
        "gemini-1.5-pro": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gemini-1.5-pro-002": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gemini-1.5-flash": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gemini-1.5-flash-002": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gemini-1.5-flash-8b": [
            "text_generation",
            "translation",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        # Gemini 1.0 series
        "gemini-1.0-pro": [
            "text_generation",
            "translation",
            "code_generation",
            "function_calling",
            "structured_output",
        ],
        # Embedding models
        "text-embedding-004": [
            "embedding",
        ],
        "embedding-001": [
            "embedding",
        ],
        # Image generation
        "imagen-3.0-generate-001": [
            "image_generation",
        ],
    },

    # -----------------------------------------------------------------------
    # OpenAI
    # -----------------------------------------------------------------------
    "openai": {
        # GPT-4o series
        "gpt-4o": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gpt-4o-2024-11-20": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gpt-4o-2024-08-06": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gpt-4o-2024-05-13": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gpt-4o-mini": [
            "text_generation",
            "translation",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gpt-4o-mini-2024-07-18": [
            "text_generation",
            "translation",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gpt-4o-audio-preview": [
            "text_generation",
            "transcription",
            "text_to_speech",
            "function_calling",
        ],
        # o-series reasoning models
        "o1": [
            "text_generation",
            "code_generation",
            "function_calling",
            "structured_output",
            "image_understanding",
        ],
        "o1-2024-12-17": [
            "text_generation",
            "code_generation",
            "function_calling",
            "structured_output",
            "image_understanding",
        ],
        "o1-mini": [
            "text_generation",
            "code_generation",
        ],
        "o1-mini-2024-09-12": [
            "text_generation",
            "code_generation",
        ],
        "o1-preview": [
            "text_generation",
            "code_generation",
        ],
        "o1-preview-2024-09-12": [
            "text_generation",
            "code_generation",
        ],
        "o3": [
            "text_generation",
            "code_generation",
            "function_calling",
            "structured_output",
            "image_understanding",
        ],
        "o3-mini": [
            "text_generation",
            "code_generation",
            "function_calling",
            "structured_output",
        ],
        "o3-mini-2025-01-31": [
            "text_generation",
            "code_generation",
            "function_calling",
            "structured_output",
        ],
        # GPT-4 Turbo series
        "gpt-4-turbo": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gpt-4-turbo-2024-04-09": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        "gpt-4-turbo-preview": [
            "text_generation",
            "translation",
            "document_processing",
            "code_generation",
            "image_understanding",
            "function_calling",
            "structured_output",
        ],
        # GPT-4 series
        "gpt-4": [
            "text_generation",
            "translation",
            "code_generation",
            "function_calling",
            "structured_output",
        ],
        "gpt-4-0613": [
            "text_generation",
            "translation",
            "code_generation",
            "function_calling",
        ],
        # GPT-3.5 series
        "gpt-3.5-turbo": [
            "text_generation",
            "translation",
            "code_generation",
            "function_calling",
            "structured_output",
        ],
        "gpt-3.5-turbo-0125": [
            "text_generation",
            "translation",
            "code_generation",
            "function_calling",
            "structured_output",
        ],
        # Audio / Transcription
        "whisper-1": [
            "transcription",
        ],
        # Text-to-Speech
        "tts-1": [
            "text_to_speech",
        ],
        "tts-1-hd": [
            "text_to_speech",
        ],
        # Image generation
        "dall-e-3": [
            "image_generation",
        ],
        "dall-e-2": [
            "image_generation",
        ],
        # Embeddings
        "text-embedding-3-large": [
            "embedding",
        ],
        "text-embedding-3-small": [
            "embedding",
        ],
        "text-embedding-ada-002": [
            "embedding",
        ],
    },
}

# ---------------------------------------------------------------------------
# Default context window sizes (tokens)
# TODO: Update as new models are released.
# ---------------------------------------------------------------------------

CONTEXT_WINDOW_DEFAULTS = {
    "claude": {
        "claude-opus-4-6": 200000,
        "claude-sonnet-4-6": 200000,
        "claude-opus-4-5": 200000,
        "claude-sonnet-4-5": 200000,
        "claude-haiku-4-5": 200000,
        "claude-3-7-sonnet-20250219": 200000,
        "claude-3-5-sonnet-20241022": 200000,
        "claude-3-5-sonnet-20240620": 200000,
        "claude-3-5-haiku-20241022": 200000,
        "claude-3-opus-20240229": 200000,
        "claude-3-sonnet-20240229": 200000,
        "claude-3-haiku-20240307": 200000,
    },
    "gemini": {
        "gemini-2.0-flash": 1048576,
        "gemini-2.0-flash-lite": 1048576,
        "gemini-2.0-flash-thinking-exp": 1048576,
        "gemini-2.0-flash-exp": 1048576,
        "gemini-2.0-pro-exp": 2097152,
        "gemini-1.5-pro": 2097152,
        "gemini-1.5-pro-002": 2097152,
        "gemini-1.5-flash": 1048576,
        "gemini-1.5-flash-002": 1048576,
        "gemini-1.5-flash-8b": 1048576,
        "gemini-1.0-pro": 32760,
        "text-embedding-004": 2048,
        "embedding-001": 2048,
        "imagen-3.0-generate-001": None,
    },
    "openai": {
        "gpt-4o": 128000,
        "gpt-4o-2024-11-20": 128000,
        "gpt-4o-2024-08-06": 128000,
        "gpt-4o-2024-05-13": 128000,
        "gpt-4o-mini": 128000,
        "gpt-4o-mini-2024-07-18": 128000,
        "gpt-4o-audio-preview": 128000,
        "o1": 200000,
        "o1-2024-12-17": 200000,
        "o1-mini": 128000,
        "o1-mini-2024-09-12": 128000,
        "o1-preview": 128000,
        "o1-preview-2024-09-12": 128000,
        "o3": 200000,
        "o3-mini": 200000,
        "o3-mini-2025-01-31": 200000,
        "gpt-4-turbo": 128000,
        "gpt-4-turbo-2024-04-09": 128000,
        "gpt-4-turbo-preview": 128000,
        "gpt-4": 8192,
        "gpt-4-0613": 8192,
        "gpt-3.5-turbo": 16385,
        "gpt-3.5-turbo-0125": 16385,
        "whisper-1": None,
        "tts-1": None,
        "tts-1-hd": None,
        "dall-e-3": None,
        "dall-e-2": None,
        "text-embedding-3-large": 8191,
        "text-embedding-3-small": 8191,
        "text-embedding-ada-002": 8191,
    },
}

# ---------------------------------------------------------------------------
# Display names
# TODO: Update as new models are released.
# ---------------------------------------------------------------------------

DISPLAY_NAMES = {
    "claude": {
        "claude-opus-4-6": "Claude Opus 4.6",
        "claude-sonnet-4-6": "Claude Sonnet 4.6",
        "claude-opus-4-5": "Claude Opus 4.5",
        "claude-sonnet-4-5": "Claude Sonnet 4.5",
        "claude-haiku-4-5": "Claude Haiku 4.5",
        "claude-3-7-sonnet-20250219": "Claude 3.7 Sonnet",
        "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
        "claude-3-5-sonnet-20240620": "Claude 3.5 Sonnet (June 2024)",
        "claude-3-5-haiku-20241022": "Claude 3.5 Haiku",
        "claude-3-opus-20240229": "Claude 3 Opus",
        "claude-3-sonnet-20240229": "Claude 3 Sonnet",
        "claude-3-haiku-20240307": "Claude 3 Haiku",
    },
    "gemini": {
        "gemini-2.0-flash": "Gemini 2.0 Flash",
        "gemini-2.0-flash-lite": "Gemini 2.0 Flash Lite",
        "gemini-2.0-flash-thinking-exp": "Gemini 2.0 Flash Thinking (Experimental)",
        "gemini-2.0-flash-exp": "Gemini 2.0 Flash (Experimental)",
        "gemini-2.0-pro-exp": "Gemini 2.0 Pro (Experimental)",
        "gemini-1.5-pro": "Gemini 1.5 Pro",
        "gemini-1.5-pro-002": "Gemini 1.5 Pro 002",
        "gemini-1.5-flash": "Gemini 1.5 Flash",
        "gemini-1.5-flash-002": "Gemini 1.5 Flash 002",
        "gemini-1.5-flash-8b": "Gemini 1.5 Flash 8B",
        "gemini-1.0-pro": "Gemini 1.0 Pro",
        "text-embedding-004": "Text Embedding 004",
        "embedding-001": "Embedding 001",
        "imagen-3.0-generate-001": "Imagen 3",
    },
    "openai": {
        "gpt-4o": "GPT-4o",
        "gpt-4o-2024-11-20": "GPT-4o (Nov 2024)",
        "gpt-4o-2024-08-06": "GPT-4o (Aug 2024)",
        "gpt-4o-2024-05-13": "GPT-4o (May 2024)",
        "gpt-4o-mini": "GPT-4o mini",
        "gpt-4o-mini-2024-07-18": "GPT-4o mini (Jul 2024)",
        "gpt-4o-audio-preview": "GPT-4o Audio Preview",
        "o1": "o1",
        "o1-2024-12-17": "o1 (Dec 2024)",
        "o1-mini": "o1-mini",
        "o1-mini-2024-09-12": "o1-mini (Sep 2024)",
        "o1-preview": "o1-preview",
        "o1-preview-2024-09-12": "o1-preview (Sep 2024)",
        "o3": "o3",
        "o3-mini": "o3-mini",
        "o3-mini-2025-01-31": "o3-mini (Jan 2025)",
        "gpt-4-turbo": "GPT-4 Turbo",
        "gpt-4-turbo-2024-04-09": "GPT-4 Turbo (Apr 2024)",
        "gpt-4-turbo-preview": "GPT-4 Turbo Preview",
        "gpt-4": "GPT-4",
        "gpt-4-0613": "GPT-4 (Jun 2023)",
        "gpt-3.5-turbo": "GPT-3.5 Turbo",
        "gpt-3.5-turbo-0125": "GPT-3.5 Turbo (Jan 2024)",
        "whisper-1": "Whisper",
        "tts-1": "TTS-1",
        "tts-1-hd": "TTS-1 HD",
        "dall-e-3": "DALL-E 3",
        "dall-e-2": "DALL-E 2",
        "text-embedding-3-large": "Text Embedding 3 Large",
        "text-embedding-3-small": "Text Embedding 3 Small",
        "text-embedding-ada-002": "Text Embedding Ada 002",
    },
}

# ---------------------------------------------------------------------------
# API endpoint configurations per provider and model type
# ---------------------------------------------------------------------------

# Default endpoints for each provider (applied when model-specific entry absent)
PROVIDER_DEFAULT_ENDPOINTS = {
    "claude": [
        {
            "endpoint_type": "messages",
            "path": "/v1/messages",
            "notes": "Anthropic native format",
        }
    ],
    "gemini": [
        {
            "endpoint_type": "generate_content",
            "path": "/v1beta/models/{model}:generateContent",
            "notes": "Google native format",
        }
    ],
    "openai": [
        {
            "endpoint_type": "chat_completions",
            "path": "/v1/chat/completions",
            "notes": "OpenAI chat format",
        }
    ],
}

# Model-specific endpoint overrides
ENDPOINTS_OVERRIDE = {
    "openai": {
        "whisper-1": [
            {
                "endpoint_type": "audio_transcriptions",
                "path": "/v1/audio/transcriptions",
                "notes": "Supports mp3, mp4, mpeg, mpga, m4a, wav, webm",
            }
        ],
        "tts-1": [
            {
                "endpoint_type": "audio_speech",
                "path": "/v1/audio/speech",
                "notes": "Returns audio stream; supports mp3, opus, aac, flac, wav, pcm",
            }
        ],
        "tts-1-hd": [
            {
                "endpoint_type": "audio_speech",
                "path": "/v1/audio/speech",
                "notes": "High-definition TTS; returns audio stream",
            }
        ],
        "dall-e-3": [
            {
                "endpoint_type": "images_generations",
                "path": "/v1/images/generations",
                "notes": "Returns image URLs or base64; supports 1024x1024, 1792x1024, 1024x1792",
            }
        ],
        "dall-e-2": [
            {
                "endpoint_type": "images_generations",
                "path": "/v1/images/generations",
                "notes": "Returns image URLs or base64",
            }
        ],
        "text-embedding-3-large": [
            {
                "endpoint_type": "embeddings",
                "path": "/v1/embeddings",
                "notes": "Returns float32 or base64-encoded vectors; up to 3072 dimensions",
            }
        ],
        "text-embedding-3-small": [
            {
                "endpoint_type": "embeddings",
                "path": "/v1/embeddings",
                "notes": "Returns float32 or base64-encoded vectors; up to 1536 dimensions",
            }
        ],
        "text-embedding-ada-002": [
            {
                "endpoint_type": "embeddings",
                "path": "/v1/embeddings",
                "notes": "Returns float32 vectors; 1536 dimensions",
            }
        ],
        "gpt-4o-audio-preview": [
            {
                "endpoint_type": "chat_completions",
                "path": "/v1/chat/completions",
                "notes": "Supports audio input and output via modalities field",
            }
        ],
    },
    "gemini": {
        "text-embedding-004": [
            {
                "endpoint_type": "embeddings",
                "path": "/v1beta/models/{model}:embedContent",
                "notes": "Google native embedding format",
            }
        ],
        "embedding-001": [
            {
                "endpoint_type": "embeddings",
                "path": "/v1beta/models/{model}:embedContent",
                "notes": "Google native embedding format (legacy)",
            }
        ],
        "imagen-3.0-generate-001": [
            {
                "endpoint_type": "images_generations",
                "path": "/v1beta/models/{model}:predict",
                "notes": "Google Vertex AI / AI Studio image generation",
            }
        ],
    },
}


def get_endpoints(provider: str, model_id: str) -> list:
    """Return endpoint config for a given provider/model, with fallback to provider default."""
    overrides = ENDPOINTS_OVERRIDE.get(provider, {})
    if model_id in overrides:
        return overrides[model_id]
    return PROVIDER_DEFAULT_ENDPOINTS.get(provider, [])


def get_capabilities(provider: str, model_id: str, doc_text: str = "") -> list:
    """
    Return capability list for a given provider/model.
    优先使用人工维护的 CAPABILITIES_FALLBACK；
    若该模型不在 fallback 中，则调用 infer_capabilities() 自动推断。
    """
    known = CAPABILITIES_FALLBACK.get(provider, {}).get(model_id)
    if known is not None:
        return known
    return infer_capabilities(model_id, doc_text)


def get_context_window(provider: str, model_id: str):
    """Return default context window token count, None if unknown."""
    return CONTEXT_WINDOW_DEFAULTS.get(provider, {}).get(model_id)


def get_display_name(provider: str, model_id: str) -> str:
    """Return human-readable display name, falling back to model_id."""
    return DISPLAY_NAMES.get(provider, {}).get(model_id, model_id)


# ---------------------------------------------------------------------------
# 自动能力推断 —— 供 fallback 中没有记录的新模型使用
# 推断规则优先级：模型名称特征 > 文档关键词 > 平台默认值
# ---------------------------------------------------------------------------

# 模型名称关键词 → 能力映射（按优先级排列）
# 注意：规则按顺序匹配，命中第一条即停止。越具体的规则放越前面。
_NAME_CAPABILITY_RULES: list = [
    # ── 专用模型（单一能力）────────────────────────────────────────────────
    (["embedding", "embed"],                        ["embedding"]),
    (["whisper"],                                   ["transcription"]),
    (["tts", "text-to-speech"],                     ["text_to_speech"]),
    (["dall-e", "dalle", "imagen", "image-gen"],    ["image_generation"]),

    # ── 音频多模态（优先于通用 gpt-4o 规则）────────────────────────────────
    # 含 "-audio-" 的模型（如 gpt-4o-audio-preview）是音频输入+输出专用模型
    (["-audio-"],                                   ["text_generation", "transcription",
                                                     "text_to_speech", "function_calling"]),

    # ── Reasoning / o-series ───────────────────────────────────────────────
    # o1-mini / o1-preview：纯文本推理，无视觉、无 function_calling
    (["o1-mini", "o1-preview"],                     ["text_generation", "code_generation"]),
    # o1 正式版：支持视觉（image_understanding）
    # 注意：必须在 o1-mini/o1-preview 规则之后，避免被误提前匹配
    (["o1"],                                        ["text_generation", "code_generation",
                                                     "function_calling", "structured_output",
                                                     "image_understanding"]),
    # o3-mini：推理模型，无视觉
    (["o3-mini"],                                   ["text_generation", "code_generation",
                                                     "function_calling", "structured_output"]),
    # o3：完整推理旗舰，支持视觉
    (["o3"],                                        ["text_generation", "code_generation",
                                                     "function_calling", "structured_output",
                                                     "image_understanding"]),

    # ── 旧版 GPT-4 快照（早于 structured_output 功能上线）──────────────────
    (["gpt-4-0613", "gpt-4-0314"],                  ["text_generation", "translation",
                                                     "code_generation", "function_calling"]),

    # ── Gemini 1.0 系列（上下文窗口小，无 image_understanding）─────────────
    # 必须在"pro"通配规则之前匹配，否则会被旗舰规则误判
    (["gemini-1.0"],                                ["text_generation", "translation",
                                                     "code_generation", "function_calling",
                                                     "structured_output"]),

    # ── 轻量型模型：支持视觉，但通常无大文档处理 ──────────────────────────
    # 关键修复：用 "-mini" 而非 "mini"，避免误匹配 "gemini"（子串问题）
    # flash-lite / haiku / flash-8b 均支持 image_understanding
    #
    # Claude Haiku 4.x 系列（haiku-4）：新增 document_processing
    # 必须在通用 haiku 规则之前匹配，避免被低能力版本规则覆盖
    # - "haiku-4" 匹配 claude-haiku-4-5 ✓
    # - 不匹配 claude-3-haiku-20240307 / claude-3-5-haiku-20241022 ✓
    (["haiku-4"],                                   ["text_generation", "translation",
                                                     "document_processing", "code_generation",
                                                     "image_understanding", "function_calling",
                                                     "structured_output"]),
    # 其他轻量型模型（3.x haiku / mini / flash-lite / flash-8b）
    (["-mini", "flash-lite", "haiku", "flash-8b"],  ["text_generation", "translation",
                                                     "code_generation", "image_understanding",
                                                     "function_calling", "structured_output"]),

    # ── 旗舰 / Pro 模型：全能力 ────────────────────────────────────────────
    (["opus", "pro", "flash", "sonnet", "gpt-4o", "gpt-4-turbo", "gemini-1.5", "gemini-2.0"],
                                                    ["text_generation", "translation",
                                                     "document_processing", "code_generation",
                                                     "image_understanding", "function_calling",
                                                     "structured_output"]),

    # ── GPT-3.5 / GPT-4 通用（无 document_processing，有 structured_output）
    (["gpt-4", "gpt-3.5"],                          ["text_generation", "translation",
                                                     "code_generation", "function_calling",
                                                     "structured_output"]),

    # ── Claude 通配（未匹配到具体版本时）──────────────────────────────────
    (["claude"],                                    ["text_generation", "translation",
                                                     "document_processing", "code_generation",
                                                     "image_understanding", "function_calling",
                                                     "structured_output"]),
]

# 文档正文关键词 → 附加能力（在名称推断结果之上叠加）
_TEXT_CAPABILITY_RULES: list = [
    (["vision", "image understanding", "visual question", "multimodal", "image input",
      "图像", "视觉"],
     "image_understanding"),
    (["function call", "tool use", "tool call", "function use", "tools"],
     "function_calling"),
    (["json mode", "structured output", "json output", "response_format",
      "schema", "结构化输出"],
     "structured_output"),
    (["200k", "200,000 token", "long document", "long context", "pdf",
      "长文档", "长上下文"],
     "document_processing"),
    (["code generation", "coding", "programming", "代码"],
     "code_generation"),
    (["translation", "multilingual", "多语言", "翻译"],
     "translation"),
    (["speech to text", "transcription", "audio transcri", "whisper"],
     "transcription"),
    (["text to speech", "tts", "audio output", "voice"],
     "text_to_speech"),
    (["image generation", "generate image", "dall", "imagen"],
     "image_generation"),
    (["embedding", "vector", "semantic search"],
     "embedding"),
]


def infer_capabilities(model_id: str, doc_text: str = "") -> list:
    """
    根据模型 ID 和可选文档文本自动推断能力列表。

    1. 遍历 _NAME_CAPABILITY_RULES，用模型名称关键词匹配，取第一个命中的规则。
    2. 对文档文本中的关键词做叠加，补充名称推断未覆盖的能力。
    3. 对结果去重并排序后返回。

    该函数仅在 CAPABILITIES_FALLBACK 中找不到该模型时被调用。
    """
    id_lower = model_id.lower()
    text_lower = doc_text.lower()
    caps: set = set()

    # Step 1: 模型名称规则匹配（取第一个命中）
    for keywords, abilities in _NAME_CAPABILITY_RULES:
        if any(kw in id_lower for kw in keywords):
            caps.update(abilities)
            break

    # 若名称规则完全未命中，给个最基础的兜底
    if not caps:
        caps.update(["text_generation", "code_generation"])

    # Step 2: 文档关键词叠加（每条规则独立判断）
    if doc_text:
        for keywords, ability in _TEXT_CAPABILITY_RULES:
            if any(kw in text_lower for kw in keywords):
                caps.add(ability)

    # 定义输出顺序，保持 JSON 可读性
    _ORDER = [
        "text_generation", "translation", "transcription", "text_to_speech",
        "image_understanding", "image_generation", "document_processing",
        "code_generation", "embedding", "function_calling", "structured_output",
    ]
    return [c for c in _ORDER if c in caps]
