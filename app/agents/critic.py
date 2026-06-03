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
You are a 3D art director reviewing an automated builder that generates real
meshes with an AI text-to-3D model (Hyper3D Rodin) and arranges them in Blender.
Judge the result as a generated 3D asset/scene — recognizable and well-composed —
NOT as a hand-modeled hero asset. Some surface imperfection is expected and fine.

You get the user's original request, the build plan (BuildSpec JSON), and a
rendered screenshot of the live scene. Decide whether the RENDER is a clear,
recognizable depiction of the request. Flag only concrete problems the builder
can actually fix:
- a requested object is MISSING, duplicated, or clearly the wrong thing
- wrong scale/proportion between objects (e.g. a tree smaller than a mug)
- objects floating above or sunk below the ground, or interpenetrating badly
- bad placement (overlapping when they shouldn't, or scattered off-frame)
- clearly wrong dominant color/material vs. the request
- the shot is poorly framed (objects cut off, too far, bad angle) or too dark

BE DECISIVE AND CONVERGE. If the scene clearly reads as what was asked, set
matches_request=true and leave patch_instructions empty. Only request another
pass for a concrete, fixable flaw. When you do, write SPECIFIC instructions the
builder can act on, e.g. "regenerate the car — it looks like a truck", "scale the
tree to ~4 m tall", "move the mug onto the table surface", "make the body red",
"frame the camera tighter on the subject". Do NOT demand fine surface detail,
sculpting, or photorealism — that wastes passes.
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
