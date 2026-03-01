# scrapers/claude_scraper.py
#
# Scrapes Anthropic's pricing and model pages for Claude models.
#
# Data sources:
#   Pricing : https://www.anthropic.com/pricing#api
#   Models  : https://docs.anthropic.com/en/docs/about-claude/models/overview

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

PRICING_URL = "https://www.anthropic.com/pricing"
MODELS_URL = "https://docs.anthropic.com/en/docs/about-claude/models/overview"

PROVIDER_INFO: Dict[str, Any] = {
    "name": "Anthropic",
    "base_url": "https://api.anthropic.com",
    "auth_method": "x-api-key",
    "sdk_support": ["anthropic"],
}

# ---------------------------------------------------------------------------
# Model-name → API-ID mapping used when the pricing page shows display names
# instead of API identifiers.
# TODO: Extend this table whenever Anthropic releases new models.
# ---------------------------------------------------------------------------
_DISPLAY_TO_ID: Dict[str, str] = {
    "claude opus 4": "claude-opus-4-6",
    "claude sonnet 4": "claude-sonnet-4-6",
    "claude haiku 4": "claude-haiku-4-5",
    "claude opus 4.6": "claude-opus-4-6",
    "claude sonnet 4.6": "claude-sonnet-4-6",
    "claude opus 4.5": "claude-opus-4-5",
    "claude sonnet 4.5": "claude-sonnet-4-5",
    "claude haiku 4.5": "claude-haiku-4-5",
    "claude 3.7 sonnet": "claude-3-7-sonnet-20250219",
    "claude 3.5 sonnet": "claude-3-5-sonnet-20241022",
    "claude 3.5 haiku": "claude-3-5-haiku-20241022",
    "claude 3 opus": "claude-3-opus-20240229",
    "claude 3 sonnet": "claude-3-sonnet-20240229",
    "claude 3 haiku": "claude-3-haiku-20240307",
}


def _normalize_model_id(raw_name: str) -> str:
    """
    Convert a display-name or partial model name into the canonical API model ID.
    Falls back to a slugified version when no mapping is found.
    """
    lower = raw_name.lower().strip()
    for pattern, model_id in _DISPLAY_TO_ID.items():
        if pattern in lower:
            return model_id
    # If the string already looks like an API ID (contains dashes, digits), keep it
    if re.search(r"claude-\w", lower):
        return lower
    return re.sub(r"\s+", "-", lower)


class ClaudeScraper(BaseScraper):
    """Scraper for Anthropic / Claude platform."""

    # ------------------------------------------------------------------
    # Pricing
    # ------------------------------------------------------------------

    def scrape_pricing(self) -> Dict[str, Dict[str, Any]]:
        """
        Parse the Anthropic pricing page and return per-model pricing data.
        Returns {} on total failure (caller will use fallback data).
        """
        # TODO: The Anthropic pricing page may require JS rendering if they add
        #       dynamic content.  Currently the page renders well with requests.
        html = self.fetch(PRICING_URL)
        if not html:
            logger.error("Claude: failed to fetch pricing page")
            return {}

        soup = BeautifulSoup(html, "lxml")
        pricing: Dict[str, Dict[str, Any]] = {}

        # Strategy 1: find <table> elements inside the API pricing section
        pricing.update(self._parse_pricing_tables(soup))

        # Strategy 2: fall back to scanning all tables on the page
        if not pricing:
            logger.warning("Claude: primary pricing section not found; scanning all tables")
            pricing.update(self._scan_all_tables_for_pricing(soup))

        # Strategy 3: regex scan on raw HTML text as last resort
        if not pricing:
            logger.warning("Claude: no tables found; falling back to regex extraction")
            pricing.update(self._regex_extract_pricing(html))

        logger.info("Claude: parsed pricing for %d models", len(pricing))
        return pricing

    def _parse_pricing_tables(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """
        Look for the API pricing section by the `#api` anchor, then parse
        any <table> elements found within that section.
        TODO: Update section-detection logic if Anthropic redesigns the page.
        """
        pricing: Dict[str, Dict[str, Any]] = {}

        # Attempt to locate the API section via id="api" or nearby heading
        api_section = soup.find(id="api")
        if api_section is None:
            # Try to find a heading containing "API" and take its parent section
            for tag in soup.find_all(["h2", "h3"]):
                if "api" in tag.get_text(strip=True).lower():
                    api_section = tag.find_parent(["section", "div", "article"])
                    if api_section:
                        break

        search_root = api_section if api_section else soup

        for table in search_root.find_all("table"):
            result = self._parse_single_pricing_table(table)
            pricing.update(result)

        return pricing

    def _scan_all_tables_for_pricing(self, soup: BeautifulSoup) -> Dict[str, Dict[str, Any]]:
        """Scan every <table> on the page and collect pricing rows."""
        pricing: Dict[str, Dict[str, Any]] = {}
        for table in soup.find_all("table"):
            result = self._parse_single_pricing_table(table)
            pricing.update(result)
        return pricing

    def _parse_single_pricing_table(self, table) -> Dict[str, Dict[str, Any]]:
        """
        Parse one <table> element.  Expects headers that contain
        'input' and 'output' (case-insensitive).
        Returns {} when no recognisable price columns are found.
        """
        pricing: Dict[str, Dict[str, Any]] = {}

        rows = table.find_all("tr")
        if not rows:
            return pricing

        # Detect header row
        headers: List[str] = []
        data_rows = []
        for i, row in enumerate(rows):
            cells = row.find_all(["th", "td"])
            texts = [c.get_text(separator=" ", strip=True).lower() for c in cells]
            if i == 0 or (not headers and any("input" in t or "output" in t for t in texts)):
                headers = texts
            else:
                data_rows.append(row)

        if not any("input" in h or "output" in h for h in headers):
            return pricing

        # Map column indices
        col_model = self._find_col(headers, ["model", "name"])
        col_input = self._find_col(headers, ["input", "prompt"])
        col_output = self._find_col(headers, ["output", "completion", "response"])
        col_cw = self._find_col(headers, ["cache write", "cache_write"])
        col_cr = self._find_col(headers, ["cache read", "cache_read", "cache hit"])

        if col_input is None and col_output is None:
            return pricing

        for row in data_rows:
            cells = row.find_all(["th", "td"])
            texts = [c.get_text(separator=" ", strip=True) for c in cells]
            if len(texts) < 2:
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
            if col_cw is not None and col_cw < len(texts):
                p["cache_write_per_1m_tokens"] = self._extract_usd_price(texts[col_cw])
            if col_cr is not None and col_cr < len(texts):
                p["cache_read_per_1m_tokens"] = self._extract_usd_price(texts[col_cr])

            if p["input_per_1m_tokens"] is not None or p["output_per_1m_tokens"] is not None:
                pricing[model_id] = p

        return pricing

    def _regex_extract_pricing(self, html: str) -> Dict[str, Dict[str, Any]]:
        """
        Last-resort regex-based extraction.
        TODO: This pattern is brittle; update if Anthropic changes their HTML.
        Looks for patterns like: 'claude-3-5-sonnet' ... '$3' ... '$15'
        """
        pricing: Dict[str, Dict[str, Any]] = {}
        # Find model IDs in the text
        model_pattern = re.compile(
            r"(claude[-\w]+\d[-\w]*)", re.IGNORECASE
        )
        price_pattern = re.compile(r"\$\s*([\d]+(?:\.[\d]+)?)")

        for m in model_pattern.finditer(html):
            model_id = m.group(1).lower()
            # Look for up to 3 prices in the next 300 chars
            snippet = html[m.end(): m.end() + 300]
            prices = price_pattern.findall(snippet)
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
        Parse the Anthropic models overview page.
        Returns {model_id: {display_name, context_window_tokens, is_deprecated}}.

        两级发现策略：
        1. 解析表格（结构化数据，含 context_window）
        2. 正则扫描 <code>/<pre>/<td> 标签中的 claude-* ID（自动发现新模型）
        """
        html = self.fetch(MODELS_URL)
        if not html:
            logger.error("Claude: failed to fetch models page")
            return {}

        soup = BeautifulSoup(html, "lxml")
        models: Dict[str, Dict[str, Any]] = {}

        # 策略 1：表格解析
        for table in soup.find_all("table"):
            result = self._parse_models_table(table)
            models.update(result)

        # 策略 2：自动发现 —— 从代码块/表格中提取 claude-* 形式的模型 ID
        # 覆盖文档改版导致表格解析失败、或 Anthropic 新增模型但尚未更新 fallback 的情况
        discovered = self.discover_model_ids(
            soup,
            r"claude-(?:opus|sonnet|haiku|instant|claude)[-\d.a-z]+",
        )
        for mid in discovered:
            if mid not in models:
                doc_text = self.extract_doc_text_for_model(soup, mid)
                models[mid] = {
                    "display_name": get_display_name("claude", mid),
                    "context_window_tokens": get_context_window("claude", mid),
                    "is_deprecated": False,
                    "_doc_text": doc_text,   # 供 build_provider_data 传给 infer_capabilities
                }
                logger.info("Claude: auto-discovered new model %s", mid)

        logger.info("Claude: total %d models (table=%d, discovered=%d)",
                    len(models),
                    len(models) - len(discovered - set(models)),
                    len(discovered))
        return models

    def _parse_models_table(self, table) -> Dict[str, Dict[str, Any]]:
        """
        Extract model information from a docs table.
        Columns typically: Model | API Name | Description | Context | Max Output | Deprecated?
        """
        models: Dict[str, Dict[str, Any]] = {}
        rows = table.find_all("tr")
        if not rows:
            return models

        headers: List[str] = []
        for i, row in enumerate(rows):
            cells = row.find_all(["th", "td"])
            texts = [c.get_text(separator=" ", strip=True) for c in cells]
            if i == 0:
                headers = [t.lower() for t in texts]
                continue

            if len(texts) < 2:
                continue

            # Identify columns
            col_api = self._find_col(headers, ["api", "model name", "model id"])
            col_display = self._find_col(headers, ["model", "name"])
            col_ctx = self._find_col(headers, ["context", "window", "input token"])
            col_deprecated = self._find_col(headers, ["deprecat", "status"])

            api_name = (
                texts[col_api].strip() if col_api is not None and col_api < len(texts) else None
            )
            display_name = (
                texts[col_display].strip()
                if col_display is not None and col_display < len(texts)
                else None
            )
            context_raw = (
                texts[col_ctx].strip()
                if col_ctx is not None and col_ctx < len(texts)
                else None
            )
            deprecated_raw = (
                texts[col_deprecated].strip()
                if col_deprecated is not None and col_deprecated < len(texts)
                else ""
            )

            # The API name column is the canonical model_id
            model_id = api_name or display_name
            if not model_id:
                continue

            # Clean up: strip any whitespace or inline code markers
            model_id = re.sub(r"[`\s]+", "", model_id)
            if not model_id:
                continue

            context_window = self._parse_context_window(context_raw) if context_raw else None
            is_deprecated = bool(
                re.search(r"deprecat|retired|legacy", deprecated_raw, re.IGNORECASE)
            )

            models[model_id] = {
                "display_name": display_name or model_id,
                "context_window_tokens": context_window,
                "is_deprecated": is_deprecated,
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

            # Collect all known model IDs: from live pages + fallback
            fallback_ids = set(CAPABILITIES_FALLBACK.get("claude", {}).keys())
            all_ids = set(pricing_data.keys()) | set(models_data.keys()) | fallback_ids

            for model_id in sorted(all_ids):
                live_info = models_data.get(model_id, {})
                pricing = pricing_data.get(model_id, self._make_empty_pricing())

                # 将文档页上下文文本传给 get_capabilities()，
                # 使自动推断能够利用页面语义（仅对 fallback 中未收录的新模型生效）
                doc_text = live_info.pop("_doc_text", "")
                capabilities = get_capabilities("claude", model_id, doc_text)

                context_window = (
                    live_info.get("context_window_tokens")
                    or get_context_window("claude", model_id)
                )
                display_name = (
                    live_info.get("display_name")
                    or get_display_name("claude", model_id)
                )
                is_deprecated = live_info.get("is_deprecated", False)

                models_list.append(
                    {
                        "model_id": model_id,
                        "display_name": display_name,
                        "context_window_tokens": context_window,
                        "capabilities": capabilities,
                        "pricing": pricing,
                        "api_endpoints": get_endpoints("claude", model_id),
                        "multilingual": True,
                        "is_deprecated": is_deprecated,
                        "notes": "",
                    }
                )

        except Exception as exc:  # noqa: BLE001
            fetch_status = "failed"
            error_message = str(exc)
            logger.error("Claude build_provider_data failed: %s", exc, exc_info=True)

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
        """Return index of first header that contains any of the given keywords."""
        for i, h in enumerate(headers):
            for kw in keywords:
                if kw in h:
                    return i
        return None
