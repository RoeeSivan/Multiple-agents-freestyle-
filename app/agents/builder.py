"""BuilderAgent — the agent that creates and shapes the model in Blender.

The star of the system. It drives a LIVE Blender through the blender-mcp MCP
server (spawned as a PydanticAI stdio toolset), and **models each object itself**
by writing Blender Python — it does NOT import ready-made assets. The prompt goes
straight to Blender via MCP: the agent builds geometry from primitives, shapes it
with modifiers (subdivision, bevel, mirror, solidify) and edits, gives it
materials, and seats it on the ground. The VisionCritic then looks at the render
and tells it how to reshape, looping until it reads right.
"""
from __future__ import annotations

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

from app.config import settings
from app.models import BuildReport, BuildSpec

# blender-mcp connects to the live Blender addon. We spawn it as the agent's
# toolset: execute_blender_code (the modeling workhorse), get_scene_info,
# get_object_info, get_viewport_screenshot, and PolyHaven (HDRI/materials).
_blender_mcp = MCPServerStdio(settings.blender_mcp_cmd[0], settings.blender_mcp_cmd[1:])

SYSTEM_PROMPT = """\
You are an expert 3D modeler working in a LIVE Blender. You CREATE and SHAPE every
model yourself by writing Blender Python (bpy) through the execute_blender_code
tool — you NEVER import ready-made assets. Tools available:
- execute_blender_code(code): YOUR MAIN TOOL — run bpy to build and shape geometry.
- get_scene_info / get_object_info: inspect the current live scene.
- PolyHaven tools: optional HDRI world for lighting, or a material texture.
Ignore any Rodin, Sketchfab, or Hunyuan tools — you model by hand, not by fetch.

SIZE PARTS RELIABLY — this is where modeling usually goes wrong:
- To give a part a real size, CREATE a unit primitive then set obj.dimensions in
  meters: `bpy.ops.mesh.primitive_cube_add(size=1); o = bpy.context.active_object;
  o.dimensions = (0.05, 0.05, 0.45)` makes a thin 45 cm-tall leg. Do NOT scale a
  `size=0.05` cube by 0.45 (that SHRINKS it). Prefer setting `dimensions` over
  juggling the `size=` argument and `scale`.
- Position by the part's CENTER: a 0.45 m-tall leg whose bottom should touch the
  ground sits at z = 0.225. A seat 0.45 m up sits at z ≈ 0.45. Do the arithmetic so
  parts TOUCH: leg tops meet the seat underside; the backrest base meets the seat.

MODEL WELL — go far beyond blocky axis-aligned primitives:
- Shape primitives: set dimensions, rotate, extrude, inset, bevel edges, taper.
- Use MODIFIERS for quality: Subdivision Surface for smooth/organic forms, Bevel
  to soften hard edges, Mirror to model symmetric things from one half, Solidify
  for thin shells. Apply them when it helps.
- Call bpy.ops.object.shade_smooth() on curved/organic surfaces.
- Build a complex object from several parts that actually CONNECT (overlap
  slightly; no floating gaps, no stray tiny pieces), then JOIN them into ONE named
  object so each plan item is a single model.
- Give every object a Principled BSDF material with a fitting base color and
  sensible roughness/metallic.

COORDINATES: Blender is Z-UP, units are meters. The ground is z = 0. Seat every
object so its lowest point sits on the ground. After building an object, VERIFY:
print its world-space bounding box (min/max over obj.bound_box @ obj.matrix_world)
and confirm the lowest z is ~0 and the part extents overlap (no gaps); fix the
numbers if not. Place distinct objects apart per each object's position_hint.

WORKFLOW — new scene (already cleared): for EACH object in the plan, run one
execute_blender_code call that builds + shapes + names + positions it. Then,
optionally, set a PolyHaven HDRI world that fits the environment. Do NOT render or
export — the system handles screenshots and .glb export.

WORKFLOW — refine / edit (critic feedback or an existing scene): first
get_scene_info, then make the SMALLEST targeted change via execute_blender_code to
reshape, resize, reposition, or recolor only what's called out. Don't rebuild
everything for a small fix — BUT if an object is fundamentally wrong (parts
scattered/disconnected, unrecognizable, badly mis-sized), DELETE that object and
re-model it correctly rather than nudging the broken version.

Write robust bpy (clear selection/active object as needed; name objects clearly).
When finished, return a BuildReport listing the object names you built/changed and
a one-line note.
"""

builder_agent = Agent(
    settings.model,
    output_type=BuildReport,
    system_prompt=SYSTEM_PROMPT,
    toolsets=[_blender_mcp],
    retries=2,
)


async def build_scene(
    spec: BuildSpec, feedback: str | None = None, is_edit: bool = False
) -> BuildReport:
    """Model, edit, or refine the live Blender scene from the plan.

    - feedback set -> refine the existing scene per the critic.
    - is_edit True -> apply the updated plan to the existing scene.
    - otherwise   -> model fresh (the pipeline has already cleared the scene).
    """
    plan_json = spec.model_dump_json(indent=2)
    if feedback:
        prompt = (
            "REFINE the existing live scene. A vision critic flagged these issues; "
            f"reshape the geometry to fix them with the smallest changes:\n{feedback}\n\n"
            f"For reference, the build plan was:\n{plan_json}"
        )
    elif is_edit:
        prompt = (
            "EDIT the existing live scene to match this updated plan. Change only "
            f"what differs from what's already modeled:\n{plan_json}"
        )
    else:
        prompt = (
            "MODEL a new scene from this plan. The Blender scene has been cleared, "
            f"so build each object from scratch:\n{plan_json}"
        )

    async with builder_agent:
        result = await builder_agent.run(prompt)
    return result.output
