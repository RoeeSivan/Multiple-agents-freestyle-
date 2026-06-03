"""VisionCritic — looks at the rendered Blender viewport and judges the result.

This closes the feedback loop. A vision-capable model sees the actual screenshot
of the live Blender scene (not just the plan), so it can catch problems only
visible after building: missing objects, wrong scale between parts, objects
floating or sunk into the ground, bad overlap, poor framing/lighting. Its
patch_instructions feed back to the BuilderAgent, which refines the live scene.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent, BinaryContent

from app.config import settings
from app.models import BuildSpec, Critique

SYSTEM_PROMPT = """\
You are a 3D art director reviewing an automated builder that MODELS each object
in Blender from scratch (primitives shaped with modifiers/edits) and arranges
them. Judge the result as a clean STYLIZED 3D model — recognizable and well-
proportioned — NOT as a photoreal hero asset. Low-poly/smooth-shaded simplicity
is fine; missing fine surface detail is fine.

You get the user's original request, the build plan (BuildSpec JSON), and a
rendered screenshot of the live scene. Decide whether the RENDER is a clear,
recognizable depiction of the request. Flag only concrete problems the builder
can reshape:
- a requested object is MISSING, or clearly reads as the wrong thing
- wrong overall SHAPE/proportions (too blocky where it should be curved, parts
  the wrong size relative to each other, a key part absent)
- parts floating apart / not connected, or the object sunk into / hovering above
  the ground
- objects overlapping or scattered off-frame; wrong relative scale between objects
- clearly wrong dominant color/material vs. the request
- the shot is poorly framed (cut off, too far) or too dark

BE DECISIVE AND CONVERGE. If the scene clearly reads as what was asked, set
matches_request=true and leave patch_instructions empty. Only request another
pass for a concrete, fixable flaw. When you do, write SPECIFIC instructions the
builder can act on, e.g. "round the car body with a subdivision modifier — it's
too boxy", "the chair back is detached, connect it to the seat", "scale the tree
to ~4 m", "make the body red", "seat the mug on the ground". Do NOT demand fine
surface detail or photorealism — that wastes passes.
"""

critic_agent = Agent(
    settings.model,
    output_type=Critique,
    system_prompt=SYSTEM_PROMPT,
    retries=2,
)


async def critique_render(request: str, spec: BuildSpec, png_path: Path) -> Critique:
    """Show the critic the render + context, get a structured verdict."""
    png_bytes = Path(png_path).read_bytes()
    result = await critic_agent.run(
        [
            f"Original request: {request}\n\n"
            f"Build plan (BuildSpec JSON):\n{spec.model_dump_json(indent=2)}\n\n"
            "Here is the rendered screenshot of the live Blender scene:",
            BinaryContent(data=png_bytes, media_type="image/png"),
        ]
    )
    return result.output
