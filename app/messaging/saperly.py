"""Saperly REST client (phone carrier for AI agents).

The published `saperly` pip package is not actually installable, so we talk to
the documented REST API directly with httpx. Base: https://saperly.com/api/v1,
Bearer auth. We use it to send SMS, resolve/inspect our line, and configure the
inbound webhook.
"""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings


class SaperlyError(RuntimeError):
    pass


@dataclass
class InboundSMS:
    """Parsed inbound 'sms_received' webhook payload."""

    from_number: str
    to_number: str
    message: str
    message_sid: str
    line_id: str

    @classmethod
    def from_payload(cls, p: dict) -> "InboundSMS":
        return cls(
            from_number=p.get("from_number", ""),
            to_number=p.get("to_number", ""),
            message=(p.get("message") or "").strip(),
            message_sid=p.get("message_sid", ""),
            line_id=p.get("line_id", ""),
        )


class SaperlyClient:
    def __init__(self, api_key: str | None = None, base: str | None = None, line_id: str | None = None):
        self.api_key = api_key or settings.saperly_api_key
        self.base = (base or settings.saperly_base).rstrip("/")
        self._line_id = line_id or settings.saperly_line_id or None

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def list_lines(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{self.base}/lines", headers=self._headers)
            if r.status_code >= 400:
                raise SaperlyError(f"list_lines failed {r.status_code}: {r.text}")
            return r.json().get("lines", [])

    async def resolve_line_id(self) -> str:
        """Return our line id, preferring the configured phone number."""
        if self._line_id:
            return self._line_id
        lines = await self.list_lines()
        if not lines:
            raise SaperlyError("no Saperly lines on this account")
        for ln in lines:
            if ln.get("phone_number") == settings.saperly_phone:
                self._line_id = ln["id"]
                return self._line_id
        self._line_id = lines[0]["id"]
        return self._line_id

    async def send_sms(self, to: str, text: str) -> dict:
        """Send an SMS from our line to `to` (E.164)."""
        line_id = await self.resolve_line_id()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(
                f"{self.base}/messages",
                headers=self._headers,
                json={"line_id": line_id, "to": to, "text": text},
            )
            if r.status_code >= 400:
                raise SaperlyError(f"send_sms failed {r.status_code}: {r.text}")
            return r.json()

    async def update_line(self, **fields) -> dict:
        """PATCH line config (e.g. webhook_url, mode)."""
        line_id = await self.resolve_line_id()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.patch(f"{self.base}/lines/{line_id}", headers=self._headers, json=fields)
            if r.status_code >= 400:
                raise SaperlyError(f"update_line failed {r.status_code}: {r.text}")
            return r.json()


# Shared default client.
saperly = SaperlyClient()
