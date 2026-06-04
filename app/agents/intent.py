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
- parts: decompose the object into its main sub-components — the structural plan
  the builder follows. For EACH part give: name, shape_hint (the primitive/form
  to start from, e.g. 'thin tapered cylinder', 'rounded box'), approx_dims_m, and
  anchor (where/how it attaches). Keep parts to the few that matter (a chair: seat,
  backrest, 4 legs). Use anchors so parts CONNECT. Leave parts empty only for a
  truly simple single-blob object.
  - approx_dims_m is a rough [x, y, z] in meters where **z is the vertical (up)
    axis**, consistent with approx_size_m. The dims MUST reflect the part's real
    ORIENTATION in the world, not just its size: an UPRIGHT part (backrest, seat
    back, door, screen, signboard, monitor panel) is TALL in z and THIN in depth —
    e.g. a bench backrest is [1.8, 0.05, 0.4], NEVER [1.8, 0.4, 0.05]; a flat
    horizontal SURFACE (seat, tabletop, shelf) is thin in z, e.g. [1.8, 0.5, 0.05].
    Sanity-check: would these dims, placed as-is, stand up or lie flat the way the
    real part does?
  - anchor says where/how the part attaches so parts CONNECT, e.g. 'on top of the
    seat', '4x mirrored under the seat corners'. For an UPRIGHT part, name the edge
    its BASE sits on and that it stands vertically, e.g. 'stands vertically along
    the rear edge of the seat, base overlapping the seat top' (optionally reclined
    a few degrees) — so the builder raises it, not lays it flat.
- proportions: the key real-world ratios (e.g. 'seat 45cm high, back ~2x seat
  height', 'wheels ~1/4 of body length') so the builder gets the look right.
- symmetry: symmetry to enforce, e.g. 'bilateral left-right', 'radial x4'; empty
  if none. (Lets the builder model one half and mirror it.)
- material_hint: surface note (e.g. 'glossy red car paint', 'rough oak wood').
  If the user names ANY color or finish (red, white, wooden, matte black,
  glossy, brushed steel…), copy it into material_hint VERBATIM — it is an
  explicit user requirement, never drop it. Keep the color in `description` too.
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
