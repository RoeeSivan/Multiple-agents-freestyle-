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
You are a 3D art director reviewing an automated builder that composes scenes
from simple primitives (box, sphere, cylinder, cone, torus, plane). Judge the
result by what LOW-POLY / STYLIZED primitives can achieve — NOT photorealism.

You get the user's original request, the SceneSpec JSON, and a rendered
screenshot. Decide whether the RENDER is a clear, recognizable depiction of the
request. Focus on structural problems that primitives CAN fix:
- floating / disconnected parts: pieces of one object must touch (a chair's
  backrest must meet the seat; foliage must sit on the trunk; wheels must touch
  the body and the ground). Flag any gap.
- sinking below or hovering above the ground
- badly wrong proportions or scale between parts
- wrong orientation (e.g. wheels should read as vertical discs)
- clearly wrong colors/materials
- unintended overlaps or objects clipping through each other

BE DECISIVE AND CONVERGE. If the scene is clearly recognizable as what was asked
— even if blocky or simplified — set matches_request=true and leave
patch_instructions empty. Only ask for another pass when there is a concrete,
fixable structural flaw. When you do, write SPECIFIC instructions with numbers
(positions in meters, sizes, rotations in radians, hex colors). NEVER ask for
textures, fine detail, smoothing, or organic sculpting — primitives cannot do
that, and demanding it just wastes passes.
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
