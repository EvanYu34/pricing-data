# scrapers/base_scraper.py
#
# Abstract base class for all platform scrapers.
# Provides shared fetch helpers (requests + Playwright) and utility methods.

import abc
import logging
import os
import random
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# User-agent pool to rotate on each request
# ---------------------------------------------------------------------------
_USER_AGENTS: List[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.3; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_3_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.3.1 Safari/605.1.15",
]

# Whether to allow Playwright fetches.
# Auto-enabled in GitHub Actions (GITHUB_ACTIONS=true) or when USE_PLAYWRIGHT=1.
_PLAYWRIGHT_ENABLED: bool = (
    os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    or os.environ.get("USE_PLAYWRIGHT", "0") == "1"
)


def _random_ua() -> str:
    return random.choice(_USER_AGENTS)


class BaseScraper(abc.ABC):
    """
    Abstract scraper base class.

    Subclasses implement:
      - scrape_pricing()  -> dict[model_id, pricing_dict]
      - scrape_models()   -> dict[model_id, model_info_dict]
      - build_provider_data() -> full provider JSON block
    """

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
            }
        )

    # ------------------------------------------------------------------
    # Public fetch interface
    # ------------------------------------------------------------------

    def fetch(self, url: str, force_playwright: bool = False) -> Optional[str]:
        """
        Fetch a URL and return raw HTML.

        Strategy:
          1. Try requests (fast, no JS).
          2. If content looks JS-gated or force_playwright=True,
             retry with Playwright (only if _PLAYWRIGHT_ENABLED).
          3. Return None if both strategies fail.
        """
        if force_playwright and _PLAYWRIGHT_ENABLED:
            logger.info("force_playwright=True, skipping requests for %s", url)
            return self._fetch_playwright(url)

        html = self._fetch_requests(url)
        if html is None:
            if _PLAYWRIGHT_ENABLED:
                logger.info("requests failed, falling back to Playwright for %s", url)
                return self._fetch_playwright(url)
            return None

        if self._needs_js(html):
            logger.info("Page appears JS-gated, retrying with Playwright for %s", url)
            if _PLAYWRIGHT_ENABLED:
                pw_html = self._fetch_playwright(url)
                if pw_html:
                    return pw_html
            # Return whatever requests got even if incomplete
            return html

        return html

    # ------------------------------------------------------------------
    # Private fetch helpers
    # ------------------------------------------------------------------

    def _fetch_requests(self, url: str, timeout: int = 30) -> Optional[str]:
        self._session.headers["User-Agent"] = _random_ua()
        try:
            time.sleep(random.uniform(0.8, 2.5))
            resp = self._session.get(url, timeout=timeout, allow_redirects=True)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as exc:
            logger.warning("requests.get(%s) failed: %s", url, exc)
            return None

    def _fetch_playwright(
        self,
        url: str,
        wait_until: str = "networkidle",
        timeout_ms: int = 60_000,
        extra_delay: float = 3.0,
    ) -> Optional[str]:
        """
        Fetch using a headless Chromium browser via Playwright.
        Applies playwright-stealth patches when the package is available.
        """
        try:
            from playwright.sync_api import sync_playwright  # noqa: PLC0415
        except ImportError:
            logger.error("playwright is not installed; cannot use headless fetch")
            return None

        try:
            stealth_sync = None
            try:
                from playwright_stealth import stealth_sync  # type: ignore  # noqa: PLC0415
            except ImportError:
                logger.warning(
                    "playwright-stealth not installed; proceeding without stealth patches"
                )

            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-accelerated-2d-canvas",
                        "--no-first-run",
                        "--no-zygote",
                        "--disable-gpu",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                ctx = browser.new_context(
                    user_agent=_random_ua(),
                    viewport={"width": 1440, "height": 900},
                    locale="en-US",
                    timezone_id="America/New_York",
                    java_script_enabled=True,
                )
                page = ctx.new_page()
                if stealth_sync is not None:
                    stealth_sync(page)

                # Random pre-navigation delay
                time.sleep(random.uniform(0.5, 1.5))
                page.goto(url, timeout=timeout_ms, wait_until=wait_until)

                # Wait for content to settle
                time.sleep(extra_delay + random.uniform(0.0, 1.5))

                html = page.content()
                browser.close()
                return html

        except Exception as exc:  # noqa: BLE001
            logger.warning("Playwright fetch(%s) failed: %s", url, exc)
            return None

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _needs_js(html: str) -> bool:
        """
        Heuristic: decide whether the HTML response needs JS rendering.
        Returns True when the body text is very sparse (< 400 chars) or the
        document is extremely short (< 3 000 bytes).
        """
        if len(html) < 3_000:
            return True
        soup = BeautifulSoup(html, "lxml")
        body = soup.find("body")
        if body is None:
            return True
        text = body.get_text(separator=" ", strip=True)
        return len(text) < 400

    @staticmethod
    def _extract_usd_price(text: str) -> Optional[float]:
        """
        Extract a USD price value from strings like:
          "$3.00 / MTok", "$ 0.075", "$15", "3.00"
        Returns the float or None.
        """
        import re  # noqa: PLC0415

        text = text.replace(",", "").strip()
        match = re.search(r"\$?\s*([\d]+(?:\.[\d]+)?)", text)
        if match:
            return float(match.group(1))
        return None

    @staticmethod
    def _parse_context_window(text: str) -> Optional[int]:
        """
        Parse token counts from strings like '200K', '1M', '128,000'.
        Returns integer token count or None.
        """
        import re  # noqa: PLC0415

        text = text.upper().replace(",", "").strip()
        m = re.search(r"([\d.]+)\s*M(?:IL|OT|EGA)?", text)
        if m:
            return int(float(m.group(1)) * 1_000_000)
        m = re.search(r"([\d.]+)\s*K", text)
        if m:
            return int(float(m.group(1)) * 1_000)
        m = re.search(r"(\d+)", text)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _make_empty_pricing() -> Dict[str, Any]:
        return {
            "currency": "USD",
            "input_per_1m_tokens": None,
            "output_per_1m_tokens": None,
            "cache_write_per_1m_tokens": None,
            "cache_read_per_1m_tokens": None,
            "notes": "",
        }

    # ------------------------------------------------------------------
    # 自动模型 ID 发现
    # ------------------------------------------------------------------

    @staticmethod
    def discover_model_ids(soup: "BeautifulSoup", pattern: str) -> set:  # type: ignore[name-defined]
        """
        在页面的 <code>、<pre>、<td>、<a> 标签中搜索匹配 pattern 的模型 ID。
        这是消除 _DISPLAY_TO_ID 硬编码字典维护成本的核心方法：
        只要文档页上出现了新模型的 API ID，下次运行时即可自动发现。

        参数
        ----
        soup    : BeautifulSoup 对象
        pattern : 正则表达式，例如 r'claude-[\\w.-]+'

        返回
        ----
        发现的模型 ID 集合（小写）
        """
        import re as _re  # noqa: PLC0415

        compiled = _re.compile(pattern, _re.IGNORECASE)
        found: set = set()

        # 优先扫描代码块和表格单元格（模型 ID 最集中的位置）
        for tag in soup.find_all(["code", "pre", "td", "th"]):
            text = tag.get_text(separator=" ", strip=True)
            for m in compiled.finditer(text):
                found.add(m.group(0).lower().strip(".,;: "))

        # 次优先：扫描全文（捕捉出现在正文段落里的模型 ID）
        full_text = soup.get_text(separator=" ")
        for m in compiled.finditer(full_text):
            candidate = m.group(0).lower().strip(".,;: ")
            # 过滤过短或明显是版本号的误匹配
            if len(candidate) >= 4 and not _re.match(r"^\d+\.\d+$", candidate):
                found.add(candidate)

        return found

    @staticmethod
    def extract_doc_text_for_model(soup: "BeautifulSoup", model_id: str, window: int = 800) -> str:  # type: ignore[name-defined]
        """
        从文档页中找到提及 model_id 的位置，提取其前后 window 个字符作为
        上下文文本，供 infer_capabilities() 做关键词扫描使用。
        """
        full = soup.get_text(separator=" ")
        idx = full.lower().find(model_id.lower())
        if idx == -1:
            return ""
        start = max(0, idx - window // 4)
        end = min(len(full), idx + window)
        return full[start:end]

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abc.abstractmethod
    def scrape_pricing(self) -> Dict[str, Dict[str, Any]]:
        """
        Scrape the platform's pricing page.
        Returns: {model_id: pricing_dict, ...}
        pricing_dict keys: currency, input_per_1m_tokens, output_per_1m_tokens,
                          cache_write_per_1m_tokens, cache_read_per_1m_tokens, notes.
        """

    @abc.abstractmethod
    def scrape_models(self) -> Dict[str, Dict[str, Any]]:
        """
        Scrape the platform's model documentation page.
        Returns: {model_id: model_info_dict, ...}
        model_info_dict keys: display_name, context_window_tokens,
                             capabilities (list), is_deprecated.
        """

    @abc.abstractmethod
    def build_provider_data(self) -> Dict[str, Any]:
        """
        Orchestrate scraping and return the full provider JSON block as
        defined in the schema (fetch_status, error_message, provider_info, models).
        """
