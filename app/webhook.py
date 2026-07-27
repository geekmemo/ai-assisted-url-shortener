import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def send_link_created_webhook(short_code: str, long_url: str, request_id: str = "-") -> None:
    if not settings.webhook_url:
        return

    try:
        httpx.post(
            settings.webhook_url,
            json={"event": "link_created", "short_code": short_code, "long_url": long_url},
            timeout=5,
        )
    except httpx.HTTPError as exc:
        logger.warning(f"request_id={request_id} webhook delivery failed for short_code={short_code}: {exc}")
