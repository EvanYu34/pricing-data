# scrapers/gemini_scraper.py
#
# Scrapes Google's Gemini API pricing and model documentation pages.
#
# Data sources:
#   Pricing : https://ai.google.dev/gemini-api/docs/pricing
#   Models  : https://ai.google.dev/gemini-api/docs/models

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

PRICING_URL = "https://ai.google.dev/gemini-api/docs/pricing"
MODELS_URL = "https://ai.google.dev/gemini-api/docs/models"

PROVIDER_INFO: Dict[str, Any] = {
    "name": "Google",
    "base_url": "https://generativelanguage.googleapis.com",
    "auth_method": "google_api_key",
    "sdk_support": ["google-generativeai", "openai"],
}

# ---------------------------------------------------------------------------
# Model name normalisation
# Maps display names / headings found on the page to canonical model IDs.
# TODO: Extend when Google releases new models.
# ---------------------------------------------------------------------------
_DISPLAY_TO_ID: Dict[str, str] = {
    "gemini 2.0 flash": "gemini-2.0-flash",
    "gemini 2.0 flash lite": "gemini-2.0-flash-lite",
    "gemini 2.0 flash-lite": "gemini-2.0-flash-lite",
    "gemini 2.0 flash thinking": "gemini-2.0-flash-thinking-exp",
    "gemini 2.0 pro": "gemini-2.0-pro-exp",
    "gemini 1.5 pro": "gemini-1.5-pro",
    "gemini 1.5 flash": "gemini-1.5-flash",
    "gemini 1.5 flash-8b": "gemini-1.5-flash-8b",
    "gemini 1.5 flash 8b": "gemini-1.5-flash-8b",
    "gemini 1.0 pro": "gemini-1.0-pro",
    "text embedding": "text-embedding-004",
    "text-embedding-004": "text-embedding-004",
    "embedding-001": "embedding-001",
    "imagen 3": "imagen-3.0-generate-001",
}


def _normalize_model_id(raw: str) -> str:
    """
    Convert a heading or display name to a canonical Gemini model ID.
    If the raw string already looks like a model ID (contains hyphens + digits),
    return it lowercased.
    """
    lower = raw.lower().strip()
    # Direct match
    if lower in _DISPLAY_TO_ID:
        return _DISPLAY_TO_ID[lower]
    # Partial match
    for pattern, model_id in _DISPLAY_TO_ID.items():
        if pattern in lower:
            return model_id
    # Already an ID-like string
    if re.match(r"gemini[-\d]|text-embedding|embedding-|imagen", lower):
        return lower
    return lower


class GeminiScraper(BaseScraper):
    """Scraper for Google Gemini API."""

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    def scrape_pricing(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch and parse the Gemini pricing page.
        Google's AI developer docs can require JS; we try requests first
        and fall back to Playwright.
        """
        html = self.fetch(PRICING_URL)
        if not html:
            logger.error("Gemini: failed to fetch pricing page")
            return {}

        soup = BeautifulSoup(html, "lxml")
        pricing: Dict[str, Dict[str, Any]] = {}

        # Strategy 1: look for embedded JSON data (some MDX-based pages inject it)
        pricing.update(self._extract_json_pricing(html))

        # Strategy 2: parse <table> elements
        if not pricing:
            pricing.update(self._parse_pricing_tables(soup))

        # Strategy 3: scan headings followed by price text
        if not pricing:
            pricing.update(self._parse_pricing_sections(soup))

        logger.info("Gemini: parsed pricing for %d models", len(pricing))
        return pricing

    def _extract_json_pricing(self, html: str) -> Dict[str, Dict[str, Any]]:
        """
        从页面内嵌的 JSON 脚本中提取定价信息。
        支持多种 Google 文档站点的数据注入格式，并使用递归树遍历，
        无需提前知道确切的 JSON 路径。
        """
        pricing: Dict[str, Dict[str, Any]] = {}

        # 候选 <script> 提取规则（按优先级排列）
        script_patterns = [
            # 1. Next.js __NEXT_DATA__
            r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            # 2. Google Devsite 常见注入格式
            r'window\.__DEVSITE_DATA__\s*=\s*(\{.*?\});\s*</script>',
            # 3. 通用 application/json script 标签
            r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
        ]

        for pattern in script_patterns:
            for m in re.finditer(pattern, html, re.DOTALL):
                try:
                    data = json.loads(m.group(1))
                except json.JSONDecodeError:
                    continue
                # 递归遍历整棵 JSON 树，无需依赖固定路径
                self._recursive_find_pricing_gemini(data, pricing)
                if pricing:
                    logger.info("Gemini: extracted %d pricing entries from JSON script", len(pricing))
                    return pricing

        return pricing

    def _recursive_find_pricing_gemini(self, node: Any, acc: Dict[str, Dict[str, Any]]) -> None:
        """
        递归遍历 JSON 树，识别包含模型名称和价格字段的叶节点对象。
        判断标准：对象同时包含模型名称类字段和价格类字段。
        """
        if isinstance(node, dict):
            keys_lower = {k.lower(): k for k in node}

            # 找模型名称字段
            name_keys = ["model", "modelid", "model_id", "name", "modelname"]
            price_keys = ["input", "output", "inputprice", "outputprice",
                          "input_price", "output_price", "price", "cost"]

            raw_name = None
            for nk in name_keys:
                if nk in keys_lower:
                    raw_name = node[keys_lower[nk]]
                    break

            has_price = any(pk in keys_lower for pk in price_keys)

            if raw_name and has_price:
                model_id = _normalize_model_id(str(raw_name))
                p = self._make_empty_pricing()
                for pk in ["input", "inputprice", "input_price"]:
                    if pk in keys_lower:
                        p["input_per_1m_tokens"] = self._coerce_float(node[keys_lower[pk]])
                        break
                for pk in ["output", "outputprice", "output_price"]:
                    if pk in keys_lower:
                        p["output_per_1m_tokens"] = self._coerce_float(node[keys_lower[pk]])
                        break
                if p["input_per_1m_tokens"] or p["output_per_1m_tokens"]:
                    acc[model_id] = p

            for v in node.values():
                self._recursive_find_pricing_gemini(v, acc)

        elif isinstance(node, list):
            for item in node:
                self._recursive_find_pricing_gemini(item, acc)

    @staticmethod
    def _coerce_float(val: Any) -> Optional[float]:
        if val is None:
            return None
        try:
            return float(str(val).replace("$", "").replace(",", "").strip())
        except ValueError:
            return None

    def _parse_pricing_tables(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """
        Find all <table> elements and extract pricing rows.
        Google's pricing tables commonly have columns:
        Model | Input (per 1M tokens) | Output (per 1M tokens) [| Context window]
        TODO: Handle tier-based pricing (free tier vs paid tier) that appears
              in two sub-rows per model.
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

                if i == 0 or (not headers and len(texts) >= 2):
                    headers = [t.lower() for t in texts]
                    continue

                if not headers or len(texts) < 2:
                    continue

                col_model = self._find_col(headers, ["model", "name"])
                col_input = self._find_col(headers, ["input", "prompt"])
                col_output = self._find_col(headers, ["output", "response", "completion"])

                if col_input is None and col_output is None:
                    continue

                raw_name = texts[col_model] if col_model is not None and col_model < len(texts) else texts[0]
                if not raw_name:
                    continue

                model_id = _normalize_model_id(raw_name)
                p = self._make_empty_pricing()

                if col_input is not None and col_input < len(texts):
                    p["input_per_1m_tokens"] = self._extract_usd_price(texts[col_input])
                if col_output is not None and col_output < len(texts):
                    p["output_per_1m_tokens"] = self._extract_usd_price(texts[col_output])

                if p["input_per_1m_tokens"] is not None or p["output_per_1m_tokens"] is not None:
                    if model_id not in pricing:
                        pricing[model_id] = p
                    else:
                        # Keep the first non-None values found (may be paid tier)
                        existing = pricing[model_id]
                        if existing["input_per_1m_tokens"] is None:
                            existing["input_per_1m_tokens"] = p["input_per_1m_tokens"]
                        if existing["output_per_1m_tokens"] is None:
                            existing["output_per_1m_tokens"] = p["output_per_1m_tokens"]

        return pricing

    def _parse_pricing_sections(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """
        Fallback: scan section headings for model names, then look for dollar amounts
        in the nearby text.
        TODO: Tune the window size (chars_ahead) if Google's page layout changes.
        """
        pricing: Dict[str, Dict[str, Any]] = {}
        price_re = re.compile(r"\$\s*([\d]+(?:\.[\d]+)?)\s*(?:/\s*(?:1M|1m|MTok|million))?")

        for heading in soup.find_all(["h2", "h3", "h4"]):
            heading_text = heading.get_text(strip=True)
            model_id = _normalize_model_id(heading_text)
            if not model_id:
                continue

            # Gather text from the next few sibling elements
            snippet = ""
            sibling = heading.find_next_sibling()
            count = 0
            while sibling and count < 6:
                snippet += sibling.get_text(separator=" ", strip=True) + " "
                sibling = sibling.find_next_sibling()
                count += 1

            prices = price_re.findall(snippet)
            if len(prices) >= 2:
                p = self._make_empty_pricing()
                p["input_per_1m_tokens"] = float(prices[0])
                p["output_per_1m_tokens"] = float(prices[1])
                pricing[model_id] = p

        return pricing

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    def scrape_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch and parse the Gemini models page to collect model IDs,
        context windows, and advertised capabilities.

        三级发现策略：
        1. 表格解析（结构化）
        2. 标题/section 布局解析
        3. 正则自动发现 gemini-*/text-embedding-*/imagen-* 模型 ID
        """
        html = self.fetch(MODELS_URL)
        if not html:
            logger.error("Gemini: failed to fetch models page")
            return {}

        soup = BeautifulSoup(html, "lxml")
        models: Dict[str, Dict[str, Any]] = {}

        # 策略 1：表格解析
        models.update(self._parse_models_tables(soup))

        # 策略 2：section 布局解析
        if not models:
            models.update(self._parse_models_sections(soup))

        # 策略 3：自动发现 —— 捕捉文档中出现的 gemini-* / text-embedding-* / imagen-* ID
        discovered = self.discover_model_ids(
            soup,
            r"(?:gemini-[\d.]+[-\w]*|text-embedding-\d+|embedding-\d+|imagen-[\d.]+[-\w]*)",
        )
        for mid in discovered:
            if mid not in models:
                doc_text = self.extract_doc_text_for_model(soup, mid)
                models[mid] = {
                    "display_name": get_display_name("gemini", mid),
                    "context_window_tokens": get_context_window("gemini", mid),
                    "is_deprecated": False,
                    "_doc_text": doc_text,
                }
                logger.info("Gemini: auto-discovered new model %s", mid)

        logger.info("Gemini: total %d models", len(models))
        return models

    def _parse_models_tables(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """
        Extract model info from documentation tables.
        TODO: Update column detection if Google changes their docs format.
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

                if not headers or len(texts) < 2:
                    continue

                col_model = self._find_col(headers, ["model", "name", "id"])
                col_ctx = self._find_col(headers, ["context", "window", "input token", "max input"])
                col_desc = self._find_col(headers, ["description", "desc", "note"])

                raw_name = texts[col_model] if col_model is not None and col_model < len(texts) else texts[0]
                model_id = _normalize_model_id(raw_name.strip())
                if not model_id:
                    continue

                context_raw = (
                    texts[col_ctx].strip() if col_ctx is not None and col_ctx < len(texts) else None
                )
                context_window = self._parse_context_window(context_raw) if context_raw else None

                models[model_id] = {
                    "display_name": get_display_name("gemini", model_id),
                    "context_window_tokens": context_window,
                    "is_deprecated": False,
                }

        return models

    def _parse_models_sections(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """
        Fallback: extract model info by looking for headings that match known
        model name patterns and gathering context window mentions nearby.
        TODO: This is a best-effort approach; section structure may change.
        """
        models: Dict[str, Dict[str, Any]] = {}
        ctx_re = re.compile(r"([\d,.]+)\s*(k|m|million|thousand)?\s*(?:token|context)", re.IGNORECASE)

        for heading in soup.find_all(["h2", "h3"]):
            text = heading.get_text(strip=True)
            model_id = _normalize_model_id(text)
            # Skip non-model headings
            if not re.match(r"gemini|text-embedding|embedding-|imagen", model_id):
                continue

            # Scan siblings for context window info
            context_window: Optional[int] = None
            sibling = heading.find_next_sibling()
            count = 0
            while sibling and count < 8:
                snippet = sibling.get_text(separator=" ", strip=True)
                m = ctx_re.search(snippet)
                if m:
                    context_window = self._parse_context_window(m.group(0))
                    if context_window:
                        break
                sibling = sibling.find_next_sibling()
                count += 1

            models[model_id] = {
                "display_name": get_display_name("gemini", model_id),
                "context_window_tokens": context_window,
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

            fallback_ids = set(CAPABILITIES_FALLBACK.get("gemini", {}).keys())
            all_ids = set(pricing_data.keys()) | set(models_data.keys()) | fallback_ids

            for model_id in sorted(all_ids):
                live_info = models_data.get(model_id, {})
                pricing = pricing_data.get(model_id, self._make_empty_pricing())
                doc_text = live_info.pop("_doc_text", "")
                capabilities = get_capabilities("gemini", model_id, doc_text)
                context_window = (
                    live_info.get("context_window_tokens")
                    or get_context_window("gemini", model_id)
                )
                display_name = live_info.get("display_name") or get_display_name("gemini", model_id)
                is_deprecated = live_info.get("is_deprecated", False)

                models_list.append(
                    {
                        "model_id": model_id,
                        "display_name": display_name,
                        "context_window_tokens": context_window,
                        "capabilities": capabilities,
                        "pricing": pricing,
                        "api_endpoints": get_endpoints("gemini", model_id),
                        "multilingual": True,
                        "is_deprecated": is_deprecated,
                        "notes": "",
                    }
                )

        except Exception as exc:  # noqa: BLE001
            fetch_status = "failed"
            error_message = str(exc)
            logger.error("Gemini build_provider_data failed: %s", exc, exc_info=True)

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
