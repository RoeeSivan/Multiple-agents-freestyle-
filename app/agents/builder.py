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

import asyncio
import logging
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

from app.agents.reference import image_content
from app.config import settings
from app.models import BuildReport, BuildSpec, Reference

log = logging.getLogger("builder")

# blender-mcp connects to the live Blender addon. We spawn it as the agent's
# toolset: execute_blender_code (the modeling workhorse), get_scene_info,
# get_object_info, get_viewport_screenshot, and PolyHaven (HDRI/materials).
_blender_mcp = MCPServerStdio(settings.blender_mcp_cmd[0], settings.blender_mcp_cmd[1:])

# A vetted bpy helper toolkit. The builder MUST paste this verbatim at the top of
# every execute_blender_code call and build ONLY through these helpers — they make
# every part a real SOLID (3 non-zero dims) placed by its CENTER, which kills the
# two failure modes we keep hitting: flat planes and parts that don't connect.
_BPY_HELPERS = '''
import bpy, bmesh, math, mathutils

def _finish(o, name, center):
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.name = name
    o.location = mathutils.Vector(center)
    bpy.context.view_layer.update()
    return o

def box(name, size, center):
    # Solid cuboid: size=(x,y,z) meters, centered at center. NEVER a flat plane.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0))
    o = bpy.context.active_object
    o.dimensions = (max(size[0], 1e-3), max(size[1], 1e-3), max(size[2], 1e-3))
    return _finish(o, name, center)

def cyl(name, radius, height, center, axis='Z', verts=48):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height, vertices=verts, location=(0, 0, 0))
    o = bpy.context.active_object
    if axis == 'X': o.rotation_euler = (0, math.radians(90), 0)
    elif axis == 'Y': o.rotation_euler = (math.radians(90), 0, 0)
    return _finish(o, name, center)

def cone(name, radius1, radius2, height, center, verts=48):
    bpy.ops.mesh.primitive_cone_add(radius1=radius1, radius2=radius2, depth=height, vertices=verts, location=(0, 0, 0))
    return _finish(bpy.context.active_object, name, center)

def sphere(name, radius, center, segments=48):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, segments=segments, ring_count=max(8, segments // 2), location=(0, 0, 0))
    o = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    return _finish(o, name, center)

def clear_named(name):
    # Delete every mesh named `name` or `name.NNN` so a rebuild never leaves a duplicate.
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and (o.name == name or o.name.startswith(name + ".")):
            bpy.data.objects.remove(o, do_unlink=True)

def join_objs(name, objs):
    objs = [o for o in objs if o is not None]
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    objs[0].name = name
    return objs[0]

def set_material(obj, color, roughness=0.5, metallic=0.0):
    m = bpy.data.materials.new(obj.name + "_mat"); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = (color[0], color[1], color[2], 1.0)
        b.inputs['Roughness'].default_value = roughness
        b.inputs['Metallic'].default_value = metallic
    obj.data.materials.clear(); obj.data.materials.append(m)

def smooth_bevel(obj, width=0.005, segments=2, subsurf=0):
    bpy.context.view_layer.objects.active = obj
    # Idempotent: drop any prior Bevel/Subsurf so refine passes never STACK them
    # (stacked subsurf explodes the poly count and the exported .glb).
    for m in list(obj.modifiers):
        if m.type in ('BEVEL', 'SUBSURF'):
            obj.modifiers.remove(m)
    bev = obj.modifiers.new("Bevel", 'BEVEL'); bev.width = width; bev.segments = max(1, min(int(segments), 3))
    subsurf = max(0, min(int(subsurf), 1))  # cap at 1 — level 2+ is overkill and heavy
    if subsurf:
        s = obj.modifiers.new("Subsurf", 'SUBSURF'); s.levels = subsurf; s.render_levels = subsurf
        bpy.ops.object.shade_smooth()

def bbox(obj):
    mn = [1e18] * 3; mx = [-1e18] * 3
    for c in obj.bound_box:
        w = obj.matrix_world @ mathutils.Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
    dims = [round(mx[i] - mn[i], 3) for i in range(3)]
    print("BBOX", obj.name, "dims", dims, "lowz", round(mn[2], 3))
    return dims
'''

SYSTEM_PROMPT = """\
You are an expert 3D modeler working in a LIVE Blender. You CREATE and SHAPE every
model yourself by writing Blender Python (bpy) through the execute_blender_code
tool — you NEVER import ready-made assets. Tools available:
- execute_blender_code(code): YOUR MAIN TOOL — run bpy to build and shape geometry.
- get_scene_info / get_object_info: inspect the current live scene.
- PolyHaven tools: optional HDRI world for lighting, or a material texture.
Ignore any Rodin, Sketchfab, or Hunyuan tools — you model by hand, not by fetch.

USE THE HELPER TOOLKIT — THIS IS MANDATORY. Begin EVERY execute_blender_code call
by pasting this block verbatim, then build using ONLY these helpers:
--- HELPER BLOCK (paste verbatim at the top of every call) ---
""" + _BPY_HELPERS + """
--- END HELPER BLOCK ---
Helpers: box(name,(x,y,z),(cx,cy,cz)) solid cuboid · cyl(name,radius,height,center,
axis) · cone(...) · sphere(name,radius,center) · join_objs(name,[objs]) ·
set_material(obj,(r,g,b),roughness,metallic) · smooth_bevel(obj,width,segments,
subsurf) · bbox(obj) prints world dims.

HARD RULES (these are why builds fail — obey them):
1. NEVER use primitive_plane_add or any 2D/flat shape for a solid part. Every part
   is a SOLID with all three dimensions > 0 — use box/cyl/cone/sphere only. A "seat"
   is a flat-ISH box like box("seat",(0.45,0.45,0.06),...), never a plane.
2. Parts must OVERLAP at their joints (push them ~1-2 cm INTO each other), never
   leave a gap. Do the center arithmetic: a part of height h centered at z has its
   bottom at z-h/2 and top at z+h/2. Make a leg's TOP sit a bit ABOVE the seat's
   bottom so they intersect.
3. ALWAYS finish each object by JOINing every one of its parts into ONE mesh with
   join_objs(plan_name, [all, the, parts]). The final scene must contain ONLY the
   planned objects — NEVER leave a loose part as its own object (no stray 'leg',
   'seat', 'cushion', 'Cylinder' objects). A floating part = a part you forgot to
   move into place and join.
4. NOTHING FLOATS. A seat/cushion sits ON the legs/base (its bottom overlaps the
   top of what holds it, not hovering above). Leg TOPS go UP INTO the seat. Before
   joining, double-check every part touches another — fix the z of any gap.
5. SIZE: the finished object's longest dimension must match its target size
   (approx_size_m, or the real reference dimension if given). Call bbox(obj) and
   check; if it's off, scale or rebuild before finishing.
6. Seat the object on the ground: its lowest z ≈ 0.

WORKED EXAMPLE — "a wooden chair" (~0.9 m tall), built correctly:
```
# (helper block pasted above)
seat = box("seat", (0.45, 0.45, 0.06), (0, 0, 0.45))          # top 0.48, bottom 0.42
legs = []
for sx in (-0.19, 0.19):
    for sy in (-0.19, 0.19):
        legs.append(cyl("leg", 0.025, 0.46, (sx, sy, 0.23)))  # 0..0.46 -> into seat
back = box("back", (0.45, 0.05, 0.45), (0, 0.20, 0.66))       # 0.435..0.885, behind seat
chair = join_objs("wooden_chair", [seat] + legs + [back])
set_material(chair, (0.55, 0.35, 0.18), roughness=0.6)         # wood
smooth_bevel(chair, width=0.006, segments=2)
bbox(chair)   # expect dims ~ [0.45, 0.49, 0.885]
```
Note how leg tops (0.46) overlap the seat bottom (0.42) and the backrest base
(0.435) overlaps the seat — nothing floats.

MODEL WELL beyond blocky primitives: rotate/scale parts, use sphere/cone for
rounded forms, and smooth_bevel(obj, subsurf=1) ONLY for genuinely smooth/organic
shapes (subsurf is capped at 1 — never stack subdivisions; it explodes the mesh).
For hard-surface objects (chairs, tables, boxes) a light bevel with subsurf=0 is
enough. Give every object a fitting Principled BSDF material via set_material.

FOLLOW THE PLAN'S STRUCTURE: each object may list `parts` (name, shape_hint,
approx_dims_m, anchor), `proportions`, and `symmetry`. Build exactly those parts at
the given dims via the helpers, place each per its `anchor` so they OVERLAP, honor
the `proportions`, then join. If `parts` is empty, compose the object yourself from
the description. Mirror symmetric parts by building both sides (e.g. the leg loop).

REFERENCE PHOTOS: you may be given real reference photos + facts. Match the real
silhouette, proportions, part layout, and dominant color/material — the reference
is ground truth, prefer it over your assumptions.

COORDINATES: Blender is Z-UP, meters, ground z = 0. Place distinct objects apart
per each object's position_hint.

WORKFLOW — new scene (already cleared): for EACH object, run one execute_blender_code
call (helper block first) that builds + overlaps + joins + names + materials it, then
calls bbox() to self-check. Optionally set a PolyHaven HDRI. Do NOT render or export
— the system handles screenshots + .glb.

WORKFLOW — refine / edit (critic/audit feedback): first get_scene_info to see the
exact object names. For each object that needs changing: call clear_named(
'<plan_name>') to remove the old version AND any leftover parts/duplicates (e.g.
'leg', 'seat', 'plastic_chair.001'), then rebuild the COMPLETE object with the
helpers — every part placed so it OVERLAPS its neighbor (legs up into the seat, the
cushion sitting ON the seat with its bottom below the seat top — nothing floating) —
and FINISH with a single join_objs(...) so the object is ONE mesh named
'<plan_name>'. After it, the scene must hold ONLY the planned objects: no loose
parts, no duplicates. Leave objects you're not changing untouched.

When finished, return a BuildReport listing the object names you built/changed and a
one-line note.
"""

builder_agent = Agent(
    settings.model,
    output_type=BuildReport,
    system_prompt=SYSTEM_PROMPT,
    toolsets=[_blender_mcp],
    retries=2,
)


async def build_scene(
    spec: BuildSpec,
    feedback: str | None = None,
    is_edit: bool = False,
    references: dict[str, Reference] | None = None,
) -> BuildReport:
    """Model, edit, or refine the live Blender scene from the plan.

    - feedback set -> refine the existing scene per the critic.
    - is_edit True -> apply the updated plan to the existing scene.
    - otherwise   -> model fresh (the pipeline has already cleared the scene).
    - references   -> real web photos/facts per object name, fed in to ground the
      build (only on fresh build / edit — not on a pure refine pass).
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

    # On a fresh build / edit, attach real reference photos + facts as grounding.
    # Each object's reference is attached under ITS name only — never carry one
    # object's photos or geometry into another's build.
    content: list = [prompt]
    if references and not feedback:
        for name, ref in references.items():
            if ref is None or not ref.images:
                continue
            note = f"Real reference for '{name}': {ref.facts}".strip()
            if ref.real_dims_m:
                note += f" Real longest dimension ~{ref.real_dims_m} m."
            content.append(note)
            for i, p in enumerate(ref.images):
                if not Path(p).exists():
                    continue
                # Tag user-supplied photos with their view so the angle is unambiguous.
                if i < len(ref.image_labels):
                    content.append(f"'{name}' — {ref.image_labels[i]} view:")
                content.append(image_content(p))

    # Spawning the blender-mcp stdio toolset can lose a cold-start race (the first
    # `uvx blender-mcp` resolves/installs the package while the MCP init handshake
    # times out -> BrokenResourceError). The connect happens before any bpy runs, so
    # a retry is safe. Back off and try again a couple times before giving up.
    payload = content if len(content) > 1 else prompt
    last_err: Exception | None = None
    for attempt in range(1, 4):
        try:
            async with builder_agent:
                result = await builder_agent.run(payload)
            return result.output
        except Exception as e:  # noqa: BLE001 — retry transient MCP-connect failures
            last_err = e
            log.warning("builder MCP attempt %d/3 failed: %s", attempt, e)
            if attempt < 3:
                await asyncio.sleep(2.0 * attempt)
    raise RuntimeError(f"builder failed after 3 attempts: {last_err}") from last_err
