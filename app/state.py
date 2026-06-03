"""In-memory per-sender session state.

Keyed by phone number so a reply ("make it blue") edits that sender's current
SceneSpec instead of starting over. Also feeds the live dashboard.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.models import SceneSpec


@dataclass
class Turn:
    role: str  # "user" | "agent"
    text: str
    ts: float = field(default_factory=time.time)


@dataclass
class Session:
    phone: str
    sid: str
    spec: SceneSpec | None = None
    turns: list[Turn] = field(default_factory=list)
    iterations: int = 0
    status: str = "idle"  # idle | building | done | error
    updated_at: float = field(default_factory=time.time)
    render_version: int = 0  # bumped each render for cache-busting

    def add_turn(self, role: str, text: str) -> None:
        self.turns.append(Turn(role, text))
        self.updated_at = time.time()


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    @staticmethod
    def sid_for(phone: str) -> str:
        return "".join(ch for ch in phone if ch.isdigit()) or "anon"

    def get(self, phone: str) -> Session:
        sid = self.sid_for(phone)
        if sid not in self._sessions:
            self._sessions[sid] = Session(phone=phone, sid=sid)
        return self._sessions[sid]

    def by_sid(self, sid: str) -> Session | None:
        return self._sessions.get(sid)

    def all(self) -> list[Session]:
        return sorted(self._sessions.values(), key=lambda s: s.updated_at, reverse=True)


store = SessionStore()
