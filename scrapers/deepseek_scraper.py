# scrapers/deepseek_scraper.py
#
# Minimal DeepSeek scraper.
#
# DeepSeek has a clean public pricing page (https://api-docs.deepseek.com/quick_start/pricing)
# but pricing already lives in `litellm` with daily community updates and full
# coverage of all 12 chat models (deepseek-chat / deepseek-reasoner /
# deepseek-v3* / deepseek-v4* / deepseek-coder / deepseek-r1). main.py's
# `_overlay_litellm_prices` step does the heavy lifting; this scraper just
# registers the known model IDs + provider info so they appear in pricing.json.
#
# When DeepSeek adds new models that litellm hasn't picked up yet, append to
# `capabilities_fallback.CAPABILITIES_FALLBACK["deepseek"]` and they auto-flow
# through here.

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
    "name": "DeepSeek",
    "base_url": "https://api.deepseek.com",
    "auth_method": "bearer_token",
    "sdk_support": ["openai"],   # OpenAI-compatible API
}


class DeepSeekScraper(BaseScraper):
    """Minimal: rely on litellm overlay for prices + capabilities_fallback
    for model IDs / capabilities / context window. No live page scrape."""

    def scrape_pricing(self) -> Dict[str, Dict[str, Any]]:
        # litellm fills this in main.py's overlay step.
        return {}

    def scrape_models(self) -> Dict[str, Dict[str, Any]]:
        # Same — fallback file is the source of truth for ID list.
        return {}

    def build_provider_data(self) -> Dict[str, Any]:
        fallback_ids = sorted(CAPABILITIES_FALLBACK.get("deepseek", {}).keys())
        models_list: List[Dict[str, Any]] = []
        for model_id in fallback_ids:
            models_list.append(
                {
                    "model_id": model_id,
                    "display_name": get_display_name("deepseek", model_id),
                    "context_window_tokens": get_context_window("deepseek", model_id),
                    "capabilities": get_capabilities("deepseek", model_id),
                    "pricing": self._make_empty_pricing(),
                    "api_endpoints": get_endpoints("deepseek", model_id),
                    "multilingual": True,
                    "is_deprecated": False,
                    "notes": "",
                }
            )
        logger.info(
            "DeepSeek: registered %d models from capabilities_fallback "
            "(prices overlaid from litellm)",
            len(models_list),
        )
        return {
            "fetch_status": "success",
            "error_message": None,
            "provider_info": PROVIDER_INFO,
            "models": models_list,
        }
