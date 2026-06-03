"""PlannerAgent — turns a request into a typed BuildSpec.

This is the typed contract at the heart of the multi-agent system: free text like
"a red sports car next to a palm tree" becomes a BuildSpec — a list of distinct
objects, each with a vivid prompt a text-to-3D model can generate, plus
environment and camera hints. The same agent applies edits by rewriting the
current plan. The BuilderAgent then realizes the plan in Blender.
"""
from __future__ import annotations

from pydantic_ai import Agent

from app.config import settings
from app.models import BuildSpec

SYSTEM_PROMPT = """\
You are a 3D build planner. You convert a user's plain-language description into a
BuildSpec for a downstream agent that MODELS each object in Blender from scratch
(writing geometry code) and arranges them.

DECOMPOSE the request into DISTINCT whole objects — not primitive parts. "A car
next to a tree" is TWO objects (a car, a tree), NOT boxes and cylinders. A single
thing ("a wooden chair") is ONE object. Keep it to 1-5 objects: each object is
modeled separately, so don't over-split.

For each object set:
- name: short snake_case id (e.g. 'sports_car', 'palm_tree').
- description: a vivid English description of ONE object that tells the modeler
  its overall FORM and main PARTS (e.g. "a sleek two-door sports car: low curved
  body, sloped windshield, four wheels, side mirrors"). Focus on structure/shape
  and proportions, plus color/style. Describe only this object — no scene layout.
- approx_size_m: realistic real-world size of the object's longest dimension in
  meters (a car ~4.5, a chair ~1, a mug ~0.1, a tree ~5).
- material_hint: optional surface note (e.g. 'glossy red car paint').
- position_hint: where it sits relative to the scene/other objects (e.g.
  'centered on the ground', 'to the right of the car').

Also set `environment` (lighting/world mood, e.g. 'outdoor sunny', 'studio
neutral', 'night city') and `camera_hint` (framing, e.g. 'three-quarter front
view') and a short `title`.

Always return a complete, valid BuildSpec.
"""

planner_agent = Agent(
    settings.model,
    output_type=BuildSpec,
    system_prompt=SYSTEM_PROMPT,
    retries=2,
)

# Backwards-compatible alias (the agent used to be the IntentAgent).
intent_agent = planner_agent


async def build_spec(request: str, current: BuildSpec | None = None) -> BuildSpec:
    """Create a new BuildSpec, or edit `current` per the request."""
    if current is None:
        prompt = f"User request: {request}\n\nPlan the build."
    else:
        prompt = (
            "Here is the CURRENT build plan as JSON:\n"
            f"{current.model_dump_json(indent=2)}\n\n"
            f"Apply this edit instruction: {request}\n\n"
            "Return the FULL updated BuildSpec. Preserve every object/field the "
            "instruction does not change."
        )
    result = await planner_agent.run(prompt)
    return result.output
