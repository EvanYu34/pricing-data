# AI Pricing Data

Automatically maintained JSON database of Claude / Gemini / OpenAI model pricing, capabilities, and API endpoint information.

A GitHub Actions workflow runs every Monday at UTC 00:00 and commits any changes to `pricing.json`.  Desktop clients can fetch the latest data with a single HTTP GET — no API key required.

---

## Client fetch URL

```
https://raw.githubusercontent.com/<YOUR_USERNAME>/<YOUR_REPO>/main/pricing.json
```

Replace `<YOUR_USERNAME>` and `<YOUR_REPO>` with your GitHub username and repository name.

Example (curl):

```bash
curl -s https://raw.githubusercontent.com/your-username/pricing-data/main/pricing.json \
  | python -m json.tool
```

---

## Local development

### Prerequisites

- Python 3.11+
- `pip install -r requirements.txt`

### Run all scrapers

```bash
python main.py
```

### Run a single provider

```bash
python main.py --provider claude
python main.py --provider gemini
python main.py --provider openai
```

### Enable Playwright locally

By default, Playwright is only activated inside GitHub Actions.  To use it
locally (useful for debugging JS-heavy pages):

```bash
# Install Playwright browsers once
python -m playwright install chromium

# Run with Playwright enabled
USE_PLAYWRIGHT=1 python main.py
```

### Output

- `pricing.json` — updated in place
- `.commit_message` — the git commit message that would be used by CI

---

## JSON schema

```jsonc
{
  "last_updated": "2025-03-01T08:00:00Z",   // ISO-8601 UTC
  "schema_version": "2.0",
  "sources": {
    "<provider>": {
      "fetch_status": "success" | "failed",
      "error_message": null | "<reason>",
      "provider_info": { ... },
      "models": [ { ... } ]
    }
  }
}
```

### Model object

| Field | Type | Description |
|---|---|---|
| `model_id` | string | Canonical API identifier (e.g. `claude-3-5-sonnet-20241022`) |
| `display_name` | string | Human-readable name |
| `context_window_tokens` | int \| null | Maximum input context in tokens |
| `capabilities` | string[] | See capability table below |
| `pricing` | object | See pricing fields below |
| `api_endpoints` | object[] | See endpoint types below |
| `multilingual` | bool | Whether the model supports non-English input/output |
| `is_deprecated` | bool | Whether the model is deprecated / retired |
| `notes` | string | Any additional notes |

### Pricing fields

| Field | Unit | Description |
|---|---|---|
| `currency` | — | Always `"USD"` |
| `input_per_1m_tokens` | USD | Cost per 1 000 000 input tokens |
| `output_per_1m_tokens` | USD | Cost per 1 000 000 output tokens |
| `cache_write_per_1m_tokens` | USD | Prompt-cache write cost (Claude) |
| `cache_read_per_1m_tokens` | USD | Prompt-cache read cost (Claude) |
| `per_minute_audio` | USD | Audio transcription cost per minute (Whisper) |
| `per_image` | USD | Image generation cost per image (DALL-E) |
| `audio_input_per_1m_tokens` | USD | Audio input cost (GPT-4o Audio) |
| `audio_output_per_1m_tokens` | USD | Audio output cost (GPT-4o Audio) |
| `notes` | string | Supplementary pricing notes |

---

## Capability definitions

| Value | Description |
|---|---|
| `text_generation` | General text generation, Q&A, writing |
| `translation` | Multi-language translation |
| `transcription` | Speech-to-text (STT) — e.g. Whisper |
| `text_to_speech` | Text-to-speech (TTS) |
| `image_understanding` | Image input, OCR, visual Q&A (multimodal) |
| `image_generation` | Image generation — e.g. DALL-E, Imagen |
| `document_processing` | Long-document understanding, PDF processing |
| `code_generation` | Code generation and debugging |
| `embedding` | Text vectorisation for retrieval / similarity |
| `function_calling` | Tool use / Function Calling support |
| `structured_output` | JSON mode or guaranteed structured output |

---

## API endpoint types

| `endpoint_type` | HTTP path | Description |
|---|---|---|
| `chat_completions` | `POST /v1/chat/completions` | OpenAI-compatible chat format |
| `messages` | `POST /v1/messages` | Anthropic native format |
| `generate_content` | `POST /v1beta/models/{model}:generateContent` | Google native format |
| `audio_transcriptions` | `POST /v1/audio/transcriptions` | Audio → text (Whisper) |
| `audio_speech` | `POST /v1/audio/speech` | Text → audio (TTS) |
| `embeddings` | `POST /v1/embeddings` | Text → vector |
| `images_generations` | `POST /v1/images/generations` | Text → image |

---

## Project structure

```
pricing-data/
├── .github/
│   └── workflows/
│       └── update_pricing.yml     # GitHub Actions — weekly auto-update
├── scrapers/
│   ├── __init__.py
│   ├── base_scraper.py            # Abstract base with fetch helpers
│   ├── claude_scraper.py          # Anthropic scraper
│   ├── gemini_scraper.py          # Google Gemini scraper
│   ├── openai_scraper.py          # OpenAI scraper
│   └── capabilities_fallback.py  # Hard-coded capability / endpoint data
├── utils/
│   ├── __init__.py
│   └── json_merger.py             # Merge logic + diff summary
├── main.py                        # CLI entry point
├── pricing.json                   # Auto-maintained data file
├── requirements.txt
└── README.md
```

---

## Adding a new provider

1. Create `scrapers/<provider>_scraper.py` extending `BaseScraper`.
2. Implement `scrape_pricing()`, `scrape_models()`, and `build_provider_data()`.
3. Register it in `main.py`'s `SCRAPERS` dict.
4. Add fallback capability / endpoint data to `scrapers/capabilities_fallback.py`.

---

## Updating fallback data

Edit `scrapers/capabilities_fallback.py` to add or correct model capability lists,
context window sizes, display names, and endpoint configurations.  These values
are used when live scraping fails or returns incomplete data.

---

## License

MIT
