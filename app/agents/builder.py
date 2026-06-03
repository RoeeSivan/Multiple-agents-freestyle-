"""BuilderAgent — the agent that actually builds in Blender.

This is the star of the new architecture. It drives a LIVE Blender through the
blender-mcp MCP server (spawned as a PydanticAI stdio toolset), so the model can
inspect the scene, run bpy code, and pull PolyHaven assets — i.e. the prompt
goes straight to Blender.

The one thing we DON'T leave to the model is the multi-step, slow Hyper3D Rodin
text->mesh flow (create job -> poll until done -> import -> rescale). That lives
in `blender_io.generate_object` and is exposed here as a single `generate_object`
tool, so the agent makes one clean call per object instead of burning tokens
polling a status API.
"""
from __future__ import annotations

import asyncio
import json

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

from app.config import settings
from app.models import BuildReport, BuildSpec
from app.rendering import blender_io

# The blender-mcp server connects to the live Blender addon on the configured
# port. We spawn it as the agent's toolset (get_scene_info, get_object_info,
# execute_blender_code, PolyHaven search/download/set_texture, etc.).
_blender_mcp = MCPServerStdio(settings.blender_mcp_cmd[0], settings.blender_mcp_cmd[1:])

SYSTEM_PROMPT = """\
You build and edit 3D scenes inside a LIVE Blender, working from a typed plan
(BuildSpec). You have these tools:
- generate_object(name, description, target_size_m): YOUR MAIN TOOL. Generates ONE
  object as a real textured mesh (Hyper3D Rodin) and imports it, rescaled so its
  longest side is ~target_size_m meters. `description` must be a vivid English
  prompt for a SINGLE object. Call it once per object in the plan.
- execute_blender_code(code): run bpy Python to ARRANGE objects (position, rotate),
  tweak materials/colors, or set up the world. This is how you place things.
- get_scene_info / get_object_info: inspect the current live scene.
- PolyHaven tools (search/download HDRIs, textures): optional polish for lighting
  and surfaces.
Ignore any Sketchfab or Hunyuan tools.

COORDINATES: Blender is Z-UP, units are meters. The ground is the plane z = 0.
Every object must REST on the ground (its bounding-box minimum z = 0) unless the
plan says it's elevated. To seat an object on the ground, compute its world-space
bounding box from obj.bound_box @ obj.matrix_world and shift its z so the lowest
point is 0. Separate distinct objects so they don't overlap; group parts that
belong together.

BUILD (new scene — already cleared):
1. Call generate_object once for each object in the plan.
2. Then run execute_blender_code to seat everything on the ground and lay it out
   per the position_hints (spread objects out; no interpenetration).
3. Optionally set a fitting PolyHaven HDRI world for the requested environment.
   Skip it if unsure — don't waste calls.
Do NOT render or export; the system handles screenshots and .glb export.

EDIT / REFINE (a scene already exists, or you're given critic feedback):
Inspect with get_scene_info first, then make the SMALLEST change that satisfies
the request — reposition/rescale or recolor via execute_blender_code, or
regenerate a single bad object with generate_object (delete the old one first).
Never rebuild the whole scene for a small edit.

Be efficient with tool calls. When finished, return a BuildReport listing the
object names you built/changed and a one-line note.
"""

builder_agent = Agent(
    settings.model,
    output_type=BuildReport,
    system_prompt=SYSTEM_PROMPT,
    toolsets=[_blender_mcp],
    retries=2,
)


@builder_agent.tool_plain
async def generate_object(name: str, description: str, target_size_m: float = 1.0) -> str:
    """Generate ONE object as a real 3D mesh via Hyper3D Rodin and import it into
    the live scene, rescaled so its longest dimension is ~target_size_m meters.

    `description` must be a vivid, self-contained English prompt for a SINGLE
    object (e.g. "a sleek red two-door sports car"). Returns the imported object's
    name and world bounding box as JSON. Call once per object; this can take up to
    a couple of minutes, so do not call it again for the same object.
    """
    info = await asyncio.to_thread(
        blender_io.generate_object,
        name=name,
        description=description,
        target_size_m=target_size_m,
    )
    return json.dumps(info)


async def build_scene(
    spec: BuildSpec, feedback: str | None = None, is_edit: bool = False
) -> BuildReport:
    """Build, edit, or refine the live Blender scene from the plan.

    - feedback set -> refine the existing scene per the critic.
    - is_edit True -> apply the updated plan to the existing scene.
    - otherwise   -> build fresh (the pipeline has already cleared the scene).
    """
    plan_json = spec.model_dump_json(indent=2)
    if feedback:
        prompt = (
            "REFINE the existing live scene. A vision critic flagged these issues; "
            f"fix them with the smallest changes possible:\n{feedback}\n\n"
            f"For reference, the build plan was:\n{plan_json}"
        )
    elif is_edit:
        prompt = (
            "EDIT the existing live scene to match this updated plan. Change only "
            f"what differs from what's already there:\n{plan_json}"
        )
    else:
        prompt = (
            "BUILD a new scene from this plan. The Blender scene has already been "
            f"cleared, so start by generating the objects:\n{plan_json}"
        )

    async with builder_agent:
        result = await builder_agent.run(prompt)
    return result.output
