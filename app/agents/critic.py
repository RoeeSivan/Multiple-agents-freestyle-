"""VisionCritic — looks at the rendered image and decides if it matches the ask.

This closes the feedback loop. A vision-capable model is shown the actual
screenshot (not just the spec), so it can catch things only visible after
rendering: wrong proportions, floating/overlapping objects, bad orientation.
Its patch_instructions feed back into IntentAgent for another pass.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent, BinaryContent

from app.config import settings
from app.models import Critique, SceneSpec

SYSTEM_PROMPT = """\
You are a meticulous 3D art director reviewing an automated scene builder.

You are given the user's original request, the SceneSpec JSON that was built,
and a rendered screenshot of that scene. Judge whether the RENDER satisfies the
request. Look at the image critically:
- object identity: is each thing recognizable?
- proportions and scale relative to each other
- placement: resting on the ground (not floating or sunk), not unintentionally
  overlapping
- orientation: e.g. wheels should be vertical discs aligned with the car;
  things that should stand up are upright
- color and material correctness
- overall readability of the scene

If it is good enough, set matches_request=true and leave patch_instructions
empty. Otherwise, list concrete issues and write SPECIFIC, actionable edit
instructions the scene designer can apply — give numbers (sizes, positions in
meters, rotations in radians, hex colors). Only request changes that primitive
meshes (box, sphere, cylinder, cone, torus, plane) can actually express; never
ask for textures, fine surface detail, or organic sculpting.
"""

critic_agent = Agent(
    settings.model,
    output_type=Critique,
    system_prompt=SYSTEM_PROMPT,
    retries=2,
)


async def critique_render(request: str, spec: SceneSpec, png_path: Path) -> Critique:
    """Show the critic the render + context, get a structured verdict."""
    png_bytes = Path(png_path).read_bytes()
    result = await critic_agent.run(
        [
            f"Original request: {request}\n\n"
            f"SceneSpec JSON:\n{spec.model_dump_json(indent=2)}\n\n"
            "Here is the rendered screenshot:",
            BinaryContent(data=png_bytes, media_type="image/png"),
        ]
    )
    return result.output
