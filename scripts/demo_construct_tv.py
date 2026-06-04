"""Render a clean PROGRESSIVE construction of a flat-screen television.

Same fixed-camera "watch it build" technique as `demo_construct` (chair):

    tv_build_1.png  screen panel (back body)
    tv_build_2.png  + display (dark front face)
    tv_build_3.png  + stand (neck + base)
    tv_build_4.png  joined + finish  (== hero)

Needs Blender open on :9876.

    uv run python -m scripts.demo_construct_tv
"""
from __future__ import annotations

from app.config import OUT_DIR
from app.rendering import blender_io as bio

_HELPERS = """
import bpy, math, mathutils

def _finish(o, name, center):
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.name = name
    o.location = mathutils.Vector(center)
    bpy.context.view_layer.update()
    return o

def box(name, size, center):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0,0,0))
    o = bpy.context.active_object
    o.dimensions = (size[0], size[1], size[2])
    return _finish(o, name, center)

def mat(obj, color, roughness, metallic=0.0, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(obj.name + "_mat"); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = (color[0], color[1], color[2], 1.0)
        b.inputs['Roughness'].default_value = roughness
        b.inputs['Metallic'].default_value = metallic
        if emit is not None:
            if 'Emission Color' in b.inputs:
                b.inputs['Emission Color'].default_value = (emit[0], emit[1], emit[2], 1.0)
            if 'Emission Strength' in b.inputs:
                b.inputs['Emission Strength'].default_value = emit_strength
    obj.data.materials.clear(); obj.data.materials.append(m)
"""

# All parts built up front -> scene bbox (and fitted camera) is constant.
_BUILD_ALL = _HELPERS + """
# BODY: thin wide panel, lifted onto the stand.
body = box("tv_body", (1.10, 0.07, 0.62), (0, 0.0, 0.51))
mat(body, (0.04, 0.04, 0.05), roughness=0.4)

# DISPLAY: dark glass face inset on the front (front of body is at y=-0.035).
screen = box("tv_screen", (1.00, 0.012, 0.54), (0, -0.041, 0.51))
mat(screen, (0.015, 0.02, 0.03), roughness=0.08, emit=(0.05, 0.10, 0.22), emit_strength=1.4)

# STAND: a neck column + a flat base on the ground.
neck = box("tv_neck", (0.12, 0.10, 0.18), (0, 0, 0.12))
mat(neck, (0.06, 0.06, 0.07), roughness=0.5)
base = box("tv_base", (0.50, 0.30, 0.04), (0, 0, 0.02))
mat(base, (0.06, 0.06, 0.07), roughness=0.5, metallic=0.2)

# Stage 1: only the body panel is visible.
for p in (screen, neck, base):
    p.hide_render = True
print("BUILT")
"""

_JOIN_POLISH = _HELPERS + """
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.hide_render = False
objs = [o for o in bpy.data.objects if o.type == 'MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
tv = objs[0]
tv.name = "television"
bev = tv.modifiers.new("Bevel", 'BEVEL'); bev.width = 0.005; bev.segments = 2
print("POLISHED")
"""


def _reveal(keys: str) -> str:
    return (
        "import bpy\n"
        f"keys = {keys}\n"
        "for o in bpy.data.objects:\n"
        "    if o.type == 'MESH' and any(k in o.name for k in keys):\n"
        "        o.hide_render = False\n"
        "print('REVEALED')\n"
    )


def main() -> int:
    if not bio.reachable():
        print("FAIL: Blender not reachable on :9876.")
        return 1
    out = OUT_DIR / "demo_tv"
    out.mkdir(parents=True, exist_ok=True)

    print("clear + build all parts (body visible)...")
    bio.clear_scene()
    bio.run_code(_BUILD_ALL)
    bio.render_png(out / "tv_build_1.png")
    print("  tv_build_1.png (screen panel)")

    bio.run_code(_reveal("['tv_screen']"))
    bio.render_png(out / "tv_build_2.png")
    print("  tv_build_2.png (+display)")

    bio.run_code(_reveal("['tv_neck', 'tv_base']"))
    bio.render_png(out / "tv_build_3.png")
    print("  tv_build_3.png (+stand)")

    bio.run_code(_JOIN_POLISH)
    bio.render_png(out / "tv_build_4.png")
    print("  tv_build_4.png (polished, joined)")

    bio.export_glb(out / "tv.glb")
    mp4 = bio.render_turntable(out / "tv.mp4")
    print(f"  glb + turntable: {mp4}")
    print("DONE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
