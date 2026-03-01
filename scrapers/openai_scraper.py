# scrapers/openai_scraper.py
#
# Scrapes OpenAI's pricing and model documentation pages.
#
# Data sources:
#   Pricing : https://openai.com/api/pricing/
#   Models  : https://platform.openai.com/docs/models
#
# IMPORTANT: The OpenAI pricing page is a React/Next.js SPA that does not
# render meaningful content in raw HTML.  Playwright is required in CI.
# When running locally without Playwright, pricing falls back entirely to
# capabilities_fallback.py.

import json
import logging
import re
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from .base_scraper import BaseScraper
from .capabilities_fallback import (
    CAPABILITIES_FALLBACK,
    get_capabilities,
    get_context_window,
    get_display_name,
    get_endpoints,
)

logger = logging.getLogger(__name__)

PRICING_URL = "https://openai.com/api/pricing/"
MODELS_URL = "https://platform.openai.com/docs/models"

PROVIDER_INFO: Dict[str, Any] = {
    "name": "OpenAI",
    "base_url": "https://api.openai.com",
    "auth_method": "bearer_token",
    "sdk_support": ["openai"],
}

# ---------------------------------------------------------------------------
# Model-ID normalisation helpers
# TODO: Update when OpenAI adds new models or renames existing ones.
# ---------------------------------------------------------------------------
_DISPLAY_TO_ID: Dict[str, str] = {
    "gpt-4o": "gpt-4o",
    "gpt-4o mini": "gpt-4o-mini",
    "gpt-4o audio": "gpt-4o-audio-preview",
    "o1": "o1",
    "o1 mini": "o1-mini",
    "o1-mini": "o1-mini",
    "o1 preview": "o1-preview",
    "o3": "o3",
    "o3 mini": "o3-mini",
    "o3-mini": "o3-mini",
    "gpt-4 turbo": "gpt-4-turbo",
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4": "gpt-4",
    "gpt-3.5 turbo": "gpt-3.5-turbo",
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "whisper": "whisper-1",
    "whisper-1": "whisper-1",
    "tts-1 hd": "tts-1-hd",
    "tts-1-hd": "tts-1-hd",
    "tts-1": "tts-1",
    "dall-e 3": "dall-e-3",
    "dall-e-3": "dall-e-3",
    "dall-e 2": "dall-e-2",
    "dall-e-2": "dall-e-2",
    "text-embedding-3-large": "text-embedding-3-large",
    "text-embedding-3-small": "text-embedding-3-small",
    "text-embedding-ada-002": "text-embedding-ada-002",
    "text embedding 3 large": "text-embedding-3-large",
    "text embedding 3 small": "text-embedding-3-small",
    "ada v2": "text-embedding-ada-002",
}


def _normalize_model_id(raw: str) -> str:
    lower = raw.lower().strip()
    if lower in _DISPLAY_TO_ID:
        return _DISPLAY_TO_ID[lower]
    for pattern, mid in _DISPLAY_TO_ID.items():
        if pattern in lower:
            return mid
    # Already looks like an ID
    if re.match(r"gpt-|o\d|whisper|tts-|dall-e|text-embedding", lower):
        return lower
    return lower


class OpenAIScraper(BaseScraper):
    """Scraper for OpenAI platform."""

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    def scrape_pricing(self) -> Dict[str, Dict[str, Any]]:
        """
        OpenAI's pricing page is a Next.js SPA.  We request it with
        force_playwright=True so Playwright is used in CI.  In local
        development (no Playwright), the requests response is parsed as a
        best-effort fallback.
        """
        html = self.fetch(PRICING_URL, force_playwright=True)
        if not html:
            logger.error("OpenAI: failed to fetch pricing page")
            return {}

        soup = BeautifulSoup(html, "lxml")
        pricing: Dict[str, Dict[str, Any]] = {}

        # Strategy 1: parse embedded Next.js JSON data
        pricing.update(self._extract_nextjs_pricing(html))

        # Strategy 2: parse rendered DOM tables
        if not pricing:
            pricing.update(self._parse_pricing_tables(soup))

        # Strategy 3: heading + adjacent price blocks
        if not pricing:
            pricing.update(self._parse_pricing_sections(soup))

        logger.info("OpenAI: parsed pricing for %d models", len(pricing))
        return pricing

    def _extract_nextjs_pricing(self, html: str) -> Dict[str, Dict[str, Any]]:
        """
        OpenAI embeds page data inside <script id="__NEXT_DATA__"> as JSON.
        This is the most reliable extraction method when available.
        TODO: The JSON path inside __NEXT_DATA__ may change between deployments.
              If pricing stops updating, inspect the live JSON structure.
        """
        pricing: Dict[str, Dict[str, Any]] = {}

        m = re.search(r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if not m:
            return pricing

        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            logger.debug("OpenAI: __NEXT_DATA__ is not valid JSON")
            return pricing

        # Recursively search for arrays that look like pricing entries
        self._recursive_find_pricing(data, pricing)
        return pricing

    def _recursive_find_pricing(self, node: Any, acc: Dict[str, Dict[str, Any]]) -> None:
        """
        递归遍历 Next.js JSON 树，识别定价节点。
        判断标准：对象同时包含模型名称类字段和价格类字段。
        覆盖 OpenAI 历史上出现过的所有字段名变体，无需硬编码 JSON 路径。
        """
        if isinstance(node, dict):
            # 用小写 key 做无歧义匹配
            keys_lower: Dict[str, str] = {k.lower(): k for k in node}

            # 模型名称候选字段（按优先级）
            _NAME_CANDIDATES = ["model", "modelid", "model_id", "slug", "name",
                                 "modelname", "model_name", "title"]
            # 输入价格候选字段
            _INPUT_CANDIDATES = ["input", "inputprice", "input_price", "inputcost",
                                  "input_cost", "promptprice", "prompt_price",
                                  "inputtokenprice", "input_token_price"]
            # 输出价格候选字段
            _OUTPUT_CANDIDATES = ["output", "outputprice", "output_price", "outputcost",
                                   "output_cost", "completionprice", "completion_price",
                                   "outputtokenprice", "output_token_price"]
            # 特殊计费字段
            _PERIMAGE_CANDIDATES  = ["perimage", "per_image", "imageprice", "image_price"]
            _PERMINUTE_CANDIDATES = ["perminute", "per_minute", "minuteprice", "minute_price",
                                      "audiominute", "audio_minute"]

            raw_name = None
            for nk in _NAME_CANDIDATES:
                if nk in keys_lower:
                    raw_name = node[keys_lower[nk]]
                    break

            has_any_price = any(
                pk in keys_lower
                for pk in _INPUT_CANDIDATES + _OUTPUT_CANDIDATES
                         + _PERIMAGE_CANDIDATES + _PERMINUTE_CANDIDATES
            )

            if raw_name and has_any_price:
                model_id = _normalize_model_id(str(raw_name))
                p = self._make_empty_pricing()

                for ik in _INPUT_CANDIDATES:
                    if ik in keys_lower:
                        p["input_per_1m_tokens"] = self._coerce_price(node[keys_lower[ik]])
                        break
                for ok in _OUTPUT_CANDIDATES:
                    if ok in keys_lower:
                        p["output_per_1m_tokens"] = self._coerce_price(node[keys_lower[ok]])
                        break
                for imgk in _PERIMAGE_CANDIDATES:
                    if imgk in keys_lower:
                        p["per_image"] = self._coerce_price(node[keys_lower[imgk]])
                        break
                for mink in _PERMINUTE_CANDIDATES:
                    if mink in keys_lower:
                        p["per_minute_audio"] = self._coerce_price(node[keys_lower[mink]])
                        break

                has_value = any(
                    p.get(k) is not None
                    for k in ["input_per_1m_tokens", "output_per_1m_tokens",
                               "per_image", "per_minute_audio"]
                )
                if has_value:
                    acc[model_id] = p

            for v in node.values():
                self._recursive_find_pricing(v, acc)

        elif isinstance(node, list):
            for item in node:
                self._recursive_find_pricing(item, acc)

    @staticmethod
    def _coerce_price(val: Any) -> Optional[float]:
        """Convert a price value that might be str, int, or float."""
        if val is None:
            return None
        try:
            return float(str(val).replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    def _parse_pricing_tables(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """
        Parse <table> elements rendered by the SPA.
        OpenAI's pricing page groups models into sections (GPT-4o, o-series,
        Audio, Embedding, Image, Fine-tuning, etc.).
        TODO: Handle per-image and per-minute pricing fields correctly.
        """
        pricing: Dict[str, Dict[str, Any]] = {}

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue

            headers: List[str] = []
            for i, row in enumerate(rows):
                cells = row.find_all(["th", "td"])
                texts = [c.get_text(separator=" ", strip=True) for c in cells]

                if i == 0:
                    headers = [t.lower() for t in texts]
                    continue

                if not headers or len(texts) < 2:
                    continue

                col_model = self._find_col(headers, ["model", "name"])
                col_input = self._find_col(headers, ["input", "prompt"])
                col_output = self._find_col(headers, ["output", "completion", "response"])
                col_audio_input = self._find_col(headers, ["audio input"])
                col_audio_output = self._find_col(headers, ["audio output"])
                col_per_image = self._find_col(headers, ["per image", "image"])
                col_per_minute = self._find_col(headers, ["per minute", "minute"])

                raw_name = texts[col_model] if col_model is not None and col_model < len(texts) else texts[0]
                if not raw_name:
                    continue

                model_id = _normalize_model_id(raw_name)
                p = self._make_empty_pricing()

                if col_input is not None and col_input < len(texts):
                    p["input_per_1m_tokens"] = self._extract_usd_price(texts[col_input])
                if col_output is not None and col_output < len(texts):
                    p["output_per_1m_tokens"] = self._extract_usd_price(texts[col_output])

                # Audio pricing (per 1M tokens, separate)
                if col_audio_input is not None and col_audio_input < len(texts):
                    val = self._extract_usd_price(texts[col_audio_input])
                    if val:
                        p["audio_input_per_1m_tokens"] = val
                if col_audio_output is not None and col_audio_output < len(texts):
                    val = self._extract_usd_price(texts[col_audio_output])
                    if val:
                        p["audio_output_per_1m_tokens"] = val

                # Per-image pricing (DALL-E)
                if col_per_image is not None and col_per_image < len(texts):
                    val = self._extract_usd_price(texts[col_per_image])
                    if val:
                        p["per_image"] = val

                # Per-minute audio pricing (Whisper)
                if col_per_minute is not None and col_per_minute < len(texts):
                    val = self._extract_usd_price(texts[col_per_minute])
                    if val:
                        p["per_minute_audio"] = val

                has_price = any(
                    p.get(k) is not None
                    for k in ["input_per_1m_tokens", "output_per_1m_tokens",
                               "per_image", "per_minute_audio"]
                )
                if has_price:
                    pricing[model_id] = p

        return pricing

    def _parse_pricing_sections(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """
        Fallback: scan headings + nearby dollar amounts.
        TODO: Tune the number of siblings scanned if the layout changes.
        """
        pricing: Dict[str, Dict[str, Any]] = {}
        price_re = re.compile(r"\$\s*([\d]+(?:\.[\d]+)?)")

        for heading in soup.find_all(["h2", "h3", "h4"]):
            text = heading.get_text(strip=True)
            model_id = _normalize_model_id(text)
            if not re.match(r"gpt-|o\d|whisper|tts-|dall-e|text-embedding", model_id):
                continue

            snippet = ""
            sibling = heading.find_next_sibling()
            count = 0
            while sibling and count < 5:
                snippet += sibling.get_text(separator=" ", strip=True) + " "
                sibling = sibling.find_next_sibling()
                count += 1

            prices = price_re.findall(snippet)
            if len(prices) >= 2:
                p = self._make_empty_pricing()
                p["input_per_1m_tokens"] = float(prices[0])
                p["output_per_1m_tokens"] = float(prices[1])
                pricing[model_id] = p
            elif len(prices) == 1:
                # Single price — could be per-image or per-minute
                p = self._make_empty_pricing()
                snippet_lower = snippet.lower()
                if "image" in snippet_lower:
                    p["per_image"] = float(prices[0])
                elif "minute" in snippet_lower:
                    p["per_minute_audio"] = float(prices[0])
                else:
                    p["input_per_1m_tokens"] = float(prices[0])
                pricing[model_id] = p

        return pricing

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    def scrape_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch and parse the OpenAI models documentation page.
        platform.openai.com 是 SPA，需要 Playwright（CI 环境自动启用）。

        三级发现策略：
        1. 表格解析（结构化）
        2. <code>/<pre> 中提取模型 ID（原 _parse_models_sections）
        3. 通用正则扫描全页（自动发现新模型 ID）
        """
        html = self.fetch(MODELS_URL, force_playwright=True)
        if not html:
            logger.error("OpenAI: failed to fetch models page")
            return {}

        soup = BeautifulSoup(html, "lxml")
        models: Dict[str, Dict[str, Any]] = {}

        # 策略 1：表格解析
        models.update(self._parse_models_tables(soup))

        # 策略 2：代码块中的模型 ID
        models.update(self._parse_models_sections(soup))

        # 策略 3：全页正则自动发现 gpt-* / o-series / whisper / tts / dall-e / embedding
        discovered = self.discover_model_ids(
            soup,
            r"(?:gpt-[\w.-]+|o\d[\w.-]*|whisper-\w+|tts-\w+|dall-e[-\w]+|"
            r"text-embedding-[\w-]+)",
        )
        for mid in discovered:
            if mid not in models:
                doc_text = self.extract_doc_text_for_model(soup, mid)
                models[mid] = {
                    "display_name": get_display_name("openai", mid),
                    "context_window_tokens": None,
                    "is_deprecated": False,
                    "_doc_text": doc_text,
                }
                logger.info("OpenAI: auto-discovered new model %s", mid)

        logger.info("OpenAI: total %d models", len(models))
        return models

    def _parse_models_tables(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """
        Extract model info from any <table> on the models documentation page.
        TODO: Columns vary by section; update keyword lists if docs change.
        """
        models: Dict[str, Dict[str, Any]] = {}

        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue

            headers: List[str] = []
            for i, row in enumerate(rows):
                cells = row.find_all(["th", "td"])
                texts = [c.get_text(separator=" ", strip=True) for c in cells]

                if i == 0:
                    headers = [t.lower() for t in texts]
                    continue

                if not headers or len(texts) < 1:
                    continue

                col_model = self._find_col(headers, ["model", "name", "id"])
                col_ctx = self._find_col(headers, ["context", "window", "max input", "max token"])

                raw_name = texts[col_model] if col_model is not None and col_model < len(texts) else texts[0]
                model_id = _normalize_model_id(raw_name.strip())
                if not model_id:
                    continue

                context_raw = (
                    texts[col_ctx].strip() if col_ctx is not None and col_ctx < len(texts) else None
                )
                context_window = self._parse_context_window(context_raw) if context_raw else None

                models[model_id] = {
                    "display_name": get_display_name("openai", model_id),
                    "context_window_tokens": context_window,
                    "is_deprecated": False,
                }

        return models

    def _parse_models_sections(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """
        Fallback: extract model IDs from code blocks or inline code spans
        on the models page (common pattern in OpenAI docs).
        TODO: Adjust selectors if OpenAI changes their docs engine.
        """
        models: Dict[str, Dict[str, Any]] = {}

        # OpenAI docs often list model IDs in <code> or <pre> blocks
        model_id_re = re.compile(
            r"\b(gpt-[\w.-]+|o\d[\w.-]*|whisper-\w+|tts-\w+|dall-e-\w+|"
            r"text-embedding-[\w-]+)\b"
        )

        for code_tag in soup.find_all(["code", "pre"]):
            text = code_tag.get_text(strip=True)
            for match in model_id_re.finditer(text):
                model_id = match.group(1).lower()
                if model_id not in models:
                    models[model_id] = {
                        "display_name": get_display_name("openai", model_id),
                        "context_window_tokens": None,
                        "is_deprecated": False,
                    }

        return models

    # ------------------------------------------------------------------
    # Provider data assembly
    # ------------------------------------------------------------------

    def build_provider_data(self) -> Dict[str, Any]:
        fetch_status = "success"
        error_message = None
        models_list: List[Dict[str, Any]] = []

        try:
            pricing_data = self.scrape_pricing()
            models_data = self.scrape_models()

            fallback_ids = set(CAPABILITIES_FALLBACK.get("openai", {}).keys())
            all_ids = set(pricing_data.keys()) | set(models_data.keys()) | fallback_ids

            for model_id in sorted(all_ids):
                live_info = models_data.get(model_id, {})
                pricing = pricing_data.get(model_id, self._make_empty_pricing())
                doc_text = live_info.pop("_doc_text", "")
                capabilities = get_capabilities("openai", model_id, doc_text)
                context_window = (
                    live_info.get("context_window_tokens")
                    or get_context_window("openai", model_id)
                )
                display_name = live_info.get("display_name") or get_display_name("openai", model_id)
                is_deprecated = live_info.get("is_deprecated", False)

                # Determine if multilingual based on capabilities
                is_multilingual = (
                    "translation" in capabilities
                    or "transcription" in capabilities
                    or model_id in {
                        "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4",
                        "gpt-3.5-turbo", "o1", "o3", "o3-mini",
                        "whisper-1",
                    }
                )

                models_list.append(
                    {
                        "model_id": model_id,
                        "display_name": display_name,
                        "context_window_tokens": context_window,
                        "capabilities": capabilities,
                        "pricing": pricing,
                        "api_endpoints": get_endpoints("openai", model_id),
                        "multilingual": is_multilingual,
                        "is_deprecated": is_deprecated,
                        "notes": self._model_notes(model_id),
                    }
                )

        except Exception as exc:  # noqa: BLE001
            fetch_status = "failed"
            error_message = str(exc)
            logger.error("OpenAI build_provider_data failed: %s", exc, exc_info=True)

        return {
            "fetch_status": fetch_status,
            "error_message": error_message,
            "provider_info": PROVIDER_INFO,
            "models": models_list,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_col(headers: List[str], keywords: List[str]) -> Optional[int]:
        for i, h in enumerate(headers):
            for kw in keywords:
                if kw in h:
                    return i
        return None

    @staticmethod
    def _model_notes(model_id: str) -> str:
        notes_map = {
            "whisper-1": "Supports 57 languages; charged per minute of audio",
            "tts-1": "6 voices: alloy, echo, fable, onyx, nova, shimmer",
            "tts-1-hd": "High-definition TTS; 6 voices",
            "dall-e-3": "Supports 1024x1024, 1792x1024, 1024x1792",
            "dall-e-2": "Supports 256x256, 512x512, 1024x1024",
            "text-embedding-ada-002": "Legacy embedding model; prefer text-embedding-3-*",
        }
        return notes_map.get(model_id, "")
