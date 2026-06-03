"""InfoAgent — gathers a missing detail before an expensive build.

A text-to-3D generation is slow and costs a Rodin credit, so when a request is
genuinely too vague to build something the user will recognize, it's worth one
quick SMS question first. This agent is deliberately CONSERVATIVE: most requests
are buildable with sensible defaults (the user can always refine by replying),
so it asks at most one batched question and only when a key detail is missing.
"""
from __future__ import annotations

from pydantic_ai import Agent

from app.config import settings
from app.models import Clarification

SYSTEM_PROMPT = """\
You decide whether a request to build a 3D model is too underspecified to attempt.

Default to needs_info=FALSE. These are services that turn text into 3D models and
the user can always tweak the result by replying, so DO NOT ask about things you
can reasonably assume (color, exact size, style, background). Only set
needs_info=TRUE when the SUBJECT ITSELF is unclear — e.g. "make me something
cool", "build a thing", "surprise me", or a request so broad you couldn't picture
one specific object/scene.

When needs_info is TRUE, write ONE short, friendly SMS question (<160 chars) that
gathers the single most important missing detail — usually "what would you like
me to build?" Bundle at most two tiny asks into that one question. Never send more
than one question. When needs_info is FALSE, leave question empty.
"""

info_agent = Agent(
    settings.model,
    output_type=Clarification,
    system_prompt=SYSTEM_PROMPT,
    retries=2,
)


async def assess(request: str, has_scene: bool) -> Clarification:
    """Decide if one clarifying question is warranted before building."""
    context = (
        "The user is editing an existing scene." if has_scene
        else "The user has no scene yet; this would start a new build."
    )
    result = await info_agent.run(f"{context}\nUser message: {request}")
    return result.output
