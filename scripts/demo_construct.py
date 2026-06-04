"""Render a clean PROGRESSIVE construction of the wooden chair for the demo video.

The refine loop is stochastic and sometimes regresses (a good chair degrades into
a floating block). For the walkthrough video we want a reliable, good-looking
"watch it build" sequence, so this builds the chair part-by-part with a FIXED
camera frame and snapshots after each stage:

    build_1.png  seat
    build_2.png  + legs
    build_3.png  + backrest (raw)
    build_4.png  joined + polished wood finish  (== hero)

Trick for constant framing: all parts are created up front (so the scene bbox —
and thus the fitted camera — never changes), and earlier stages just `hide_render`
the parts that haven't "appeared" yet. Then we join + bevel + shade-smooth for the
final, export the .glb, and render the turntable. Needs Blender open on :9876.

    uv run python -m scripts.demo_construct
"""
from __future__ import annotations

from app.config import OUT_DIR
from app.rendering import blender_io as bio

WOOD = (0.58, 0.40, 0.24)  # warm oak

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

def cyl(name, radius, height, center):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=height, vertices=48, location=(0,0,0))
    return _finish(bpy.context.active_object, name, center)

def wood(obj, color):
    m = bpy.data.materials.new(obj.name + "_mat"); m.use_nodes = True
    b = m.node_tree.nodes.get('Principled BSDF')
    if b:
        b.inputs['Base Color'].default_value = (color[0], color[1], color[2], 1.0)
        b.inputs['Roughness'].default_value = 0.45
        b.inputs['Metallic'].default_value = 0.0
    obj.data.materials.clear(); obj.data.materials.append(m)
"""

_BUILD_ALL = _HELPERS + f"""
WOOD = {WOOD}

# Build EVERY part up front so the scene bbox (and the fitted camera) is constant.
seat = box("seat", (0.42, 0.42, 0.06), (0, 0, 0.45))
legs = []
for sx in (-0.18, 0.18):
    for sy in (-0.18, 0.18):
        legs.append(cyl("leg_%s_%s" % (sx, sy), 0.025, 0.45, (sx, sy, 0.225)))
backrest = box("backrest", (0.42, 0.05, 0.5), (0, 0.185, 0.73))
# Gentle curve: bow the backrest back along its height.
for v in backrest.data.vertices:
    v.co.y -= (v.co.z ** 2) * 0.25

parts = [seat] + legs + [backrest]
for p in parts:
    wood(p, WOOD)

# Stage 1: only the seat is visible.
for p in legs + [backrest]:
    p.hide_render = True
print("BUILT")
"""


def _reveal(names_visible_extra: str) -> str:
    """bpy that un-hides the named parts (substring match)."""
    return (
        "import bpy\n"
        f"keys = {names_visible_extra}\n"
        "for o in bpy.data.objects:\n"
        "    if o.type == 'MESH' and any(k in o.name for k in keys):\n"
        "        o.hide_render = False\n"
        "print('REVEALED')\n"
    )


_JOIN_POLISH = _HELPERS + """
# Reveal everything, join into one solid object, polish: bevel + smooth shading.
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.hide_render = False
objs = [o for o in bpy.data.objects if o.type == 'MESH']
bpy.ops.object.select_all(action='DESELECT')
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
chair = objs[0]
chair.name = "wooden_chair"
bev = chair.modifiers.new("Bevel", 'BEVEL'); bev.width = 0.006; bev.segments = 2
bpy.context.view_layer.objects.active = chair
bpy.ops.object.shade_smooth()
print("POLISHED")
"""


def main() -> int:
    if not bio.reachable():
        print("FAIL: Blender not reachable on :9876.")
        return 1
    out = OUT_DIR / "demo_chair"
    out.mkdir(parents=True, exist_ok=True)

    print("clear + build all parts (seat visible)...")
    bio.clear_scene()
    bio.run_code(_BUILD_ALL)
    bio.render_png(out / "build_1.png")
    print("  build_1.png (seat)")

    bio.run_code(_reveal("['leg_']"))
    bio.render_png(out / "build_2.png")
    print("  build_2.png (+legs)")

    bio.run_code(_reveal("['backrest']"))
    bio.render_png(out / "build_3.png")
    print("  build_3.png (+backrest)")

    bio.run_code(_JOIN_POLISH)
    bio.render_png(out / "build_4.png")
    print("  build_4.png (polished, joined)")

    bio.export_glb(out / "chair.glb")
    mp4 = bio.render_turntable(out / "chair.mp4")
    print(f"  glb + turntable: {mp4}")
    print("DONE.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
