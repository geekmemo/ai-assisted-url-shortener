import httpx

from app.config import settings


def send_link_created_webhook(short_code: str, long_url: str) -> None:
    if not settings.webhook_url:
        return

    try:
        httpx.post(
            settings.webhook_url,
            json={"event": "link_created", "short_code": short_code, "long_url": long_url},
            timeout=5,
        )
    except httpx.HTTPError:
        pass
