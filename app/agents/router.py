"""RouterAgent — the front-desk agent.

Classifies each inbound SMS so the system reacts well: build a NEW scene, EDIT
the current one, or just CHAT (greeting/thanks/help) without burning a render.
Demonstrates multi-agent collaboration: this agent decides, then hands off to
IntentAgent + VisionCritic.
"""
from __future__ import annotations

from typing import Literal

from pydantic_ai import Agent
from pydantic import BaseModel, Field

from app.config import settings


class Route(BaseModel):
    action: Literal["new", "edit", "chat"] = Field(
        description="'new' = build a fresh scene; 'edit' = modify the current "
        "scene; 'chat' = greeting/thanks/question with no build intent"
    )
    reply: str = Field(
        default="",
        description="for action='chat' only: a short, friendly SMS reply guiding "
        "the user to describe a 3D scene",
    )


SYSTEM_PROMPT = """\
You triage SMS messages for a service that builds 3D models from text.

Classify the message into one action:
- "new": the user describes a thing/scene to build, or asks to start over.
- "edit": the user asks to change the CURRENT scene (e.g. "make it blue",
  "bigger wheels", "add a tree"). Only valid if a scene already exists.
- "chat": greetings, thanks, small talk, or questions about what this does —
  anything with no actual build/edit request.

If a scene does NOT exist yet, never choose "edit"; an underspecified change
request with no scene is itself a "chat" (ask them what to build).

For "chat", write a short, warm reply (one or two sentences) that nudges them to
text a description like "a red sports car on a beach". Leave reply empty
otherwise.
"""

router_agent = Agent(
    settings.model,
    output_type=Route,
    system_prompt=SYSTEM_PROMPT,
    retries=2,
)


async def route_message(message: str, has_scene: bool) -> Route:
    scene_state = "A scene already exists." if has_scene else "No scene exists yet."
    result = await router_agent.run(f"{scene_state}\nUser SMS: {message}")
    return result.output
