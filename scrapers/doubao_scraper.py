# scrapers/doubao_scraper.py
#
# Minimal 豆包 / Doubao (Volcengine) scraper.
#
# Doubao publishes pricing on Volcengine's docs portal in Chinese
# (https://www.volcengine.com/docs/82379/1099475) — a JS-rendered
# multi-tab page that's painful to parse. litellm tracks the volcengine
# namespace but for chat models (doubao-seed-*) all price fields are
# currently null. So:
#
#   - Model ID registration: `capabilities_fallback.CAPABILITIES_FALLBACK["doubao"]`
#   - Prices: `capabilities_fallback.PRICING_FALLBACK["doubao"]` (hand-curated
#     from Volcengine docs, with `_source_url` in notes so it can be re-verified)
#   - Provider block: this scraper just assembles `models[]`
#
# When Volcengine simplifies their pricing page or litellm starts filling the
# doubao-seed-* prices, swap this for a real fetch.

import logging
from typing import Any, Dict, List

from .base_scraper import BaseScraper
from .capabilities_fallback import (
    CAPABILITIES_FALLBACK,
    get_capabilities,
    get_context_window,
    get_display_name,
    get_endpoints,
)

logger = logging.getLogger(__name__)

PROVIDER_INFO: Dict[str, Any] = {
    "name": "Doubao (Volcengine)",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "auth_method": "bearer_token",
    "sdk_support": ["openai", "volcengine-python-sdk"],   # OpenAI-compatible
}


class DoubaoScraper(BaseScraper):
    """Capabilities-only — no live scrape. Volcengine docs page is JS-heavy +
    Chinese-only; not worth the playwright spend until prices stabilise."""

    def scrape_pricing(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def scrape_models(self) -> Dict[str, Dict[str, Any]]:
        return {}

    def build_provider_data(self) -> Dict[str, Any]:
        fallback_ids = sorted(CAPABILITIES_FALLBACK.get("doubao", {}).keys())
        models_list: List[Dict[str, Any]] = []
        for model_id in fallback_ids:
            models_list.append(
                {
                    "model_id": model_id,
                    "display_name": get_display_name("doubao", model_id),
                    "context_window_tokens": get_context_window("doubao", model_id),
                    "capabilities": get_capabilities("doubao", model_id),
                    "pricing": self._make_empty_pricing(),
                    "api_endpoints": get_endpoints("doubao", model_id),
                    "multilingual": True,
                    "is_deprecated": False,
                    "notes": "",
                }
            )
        logger.info(
            "Doubao: registered %d models from capabilities_fallback "
            "(prices via PRICING_FALLBACK; litellm volcengine entries are null)",
            len(models_list),
        )
        return {
            "fetch_status": "success",
            "error_message": None,
            "provider_info": PROVIDER_INFO,
            "models": models_list,
        }
