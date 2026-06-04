"""In-memory per-sender session state.

Keyed by phone number so a reply ("make it blue") edits that sender's current
BuildSpec instead of starting over. Also feeds the live dashboard.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.models import BuildSpec


@dataclass
class Turn:
    role: str  # "user" | "agent"
    text: str
    ts: float = field(default_factory=time.time)


@dataclass
class ObjectIntake:
    """Photos we're collecting for ONE object, in the order the agent requests them."""

    name: str  # ObjectBrief.name (snake_case id)
    label: str  # human label shown in the upload wizard, e.g. "wooden chair"
    views: list[str]  # ordered view keys to collect, e.g. ["front", "back", "side"]
    prompts: dict[str, str]  # view -> friendly request text
    received: dict[str, str] = field(default_factory=dict)  # view -> local file path

    def missing(self) -> list[str]:
        return [v for v in self.views if v not in self.received]


@dataclass
class PhotoIntake:
    """A parked build waiting on user-supplied photos (collected via the upload link).

    Only objects the ViewPlanner flagged `needs_photos` live here; objects that don't
    need photos are left to the normal (web) reference path at build time.
    """

    id: str  # unique per intake (timestamp); namespaces the photo dir -> no cross-build bleed
    request: str  # original user text, replayed into the build
    is_edit: bool  # whether this edits an existing scene
    spec: BuildSpec  # the already-planned spec (we don't re-plan after photos arrive)
    objects: list[ObjectIntake] = field(default_factory=list)

    def find(self, name: str) -> ObjectIntake | None:
        return next((o for o in self.objects if o.name == name), None)

    def needed(self) -> list[tuple[str, str]]:
        """(object_name, view) pairs still missing, in request order."""
        return [(o.name, v) for o in self.objects for v in o.missing()]

    def complete(self) -> bool:
        return not self.needed()


@dataclass
class Session:
    phone: str
    sid: str
    spec: BuildSpec | None = None
    turns: list[Turn] = field(default_factory=list)
    iterations: int = 0
    status: str = "idle"  # idle | building | awaiting_photos | done | error
    updated_at: float = field(default_factory=time.time)
    render_version: int = 0  # bumped each build for cache-busting
    # InfoAgent flow: when we've asked one clarifying question, stash the original
    # request here so the next inbound reply is merged into it (we ask at most once).
    awaiting_clarification: bool = False
    pending_request: str = ""
    # Photo-intake flow: a parked build waiting on user photos (None when inactive).
    intake: PhotoIntake | None = None

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
