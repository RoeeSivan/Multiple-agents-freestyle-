"""Point the Saperly line's inbound-SMS webhook at this server.

Reads PUBLIC_URL from .env and PATCHes the line's webhook_url to
PUBLIC_URL/sms/incoming. Run after starting ngrok and updating PUBLIC_URL.

    uv run python -m scripts.set_webhook
"""
from __future__ import annotations

import asyncio

from app.config import settings
from app.messaging import saperly


async def main() -> None:
    if not settings.public_url:
        raise SystemExit("PUBLIC_URL is not set in .env (set it to your ngrok https URL).")
    url = f"{settings.public_url}/sms/incoming"
    line_id = await saperly.resolve_line_id()
    res = await saperly.update_line(webhook_url=url)
    print(f"line_id      : {line_id}")
    print(f"webhook_url  : {url}")
    print(f"api response : {res}")


if __name__ == "__main__":
    asyncio.run(main())
