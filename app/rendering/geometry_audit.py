"""Deterministic geometry audit — the measured half of the refine loop.

No LLM. After the builder runs, this measures the live scene with bpy and reports
exact problems the critic's eyes can miss or only describe vaguely: an object
mis-sized vs. its target, parts that float apart (scattered), empty/degenerate
meshes, or a planned object missing entirely. Its `problems` feed back to the
builder as precise instructions ("scale chair by ~0.43x: it is 9.4 m, target 4 m")
alongside the perceptual critic feedback — so mis-size/scatter get caught without
spending a vision pass, and the builder's own (unenforced) bbox check becomes real.
"""
from __future__ import annotations

import json

from app.models import BuildSpec, GeometryAudit, ObjectAudit
from app.rendering import blender_io

# Geometry that drifts more than this from its target longest dimension is flagged.
_SIZE_TOLERANCE = 1.5  # i.e. >1.5x too big or <1/1.5 too small

# bpy run inside Blender: measure every mesh object and emit JSON between markers.
# Per object: world bbox dims, lowest z, connected-component (island) count, and a
# count of island GROUPS where islands are merged when their world bboxes overlap
# (so legs that overlap-and-join read as one group; a detached part reads as a
# separate group => scattered). This is robust to "overlap then join" (which never
# welds verts), unlike a raw island count.
_AUDIT_CODE = """
import bpy, bmesh, mathutils, json
from collections import defaultdict

def _components(bm):
    parent = list(range(len(bm.verts)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for e in bm.edges:
        a, b = e.verts[0].index, e.verts[1].index
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    groups = defaultdict(list)
    for v in bm.verts:
        groups[find(v.index)].append(v)
    return list(groups.values())

out = []
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    me = o.data
    if me is None or len(me.vertices) == 0:
        out.append({"name": o.name, "dims_m": [0, 0, 0], "longest_dim_m": 0.0,
                    "lowest_z_m": 0.0, "island_count": 0, "scatter_groups": 0,
                    "has_geometry": False})
        continue
    mw = o.matrix_world
    mn = [1e18, 1e18, 1e18]; mx = [-1e18, -1e18, -1e18]
    for c in o.bound_box:
        w = mw @ mathutils.Vector(c)
        for i in range(3):
            mn[i] = min(mn[i], w[i]); mx[i] = max(mx[i], w[i])
    dims = [mx[i] - mn[i] for i in range(3)]

    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    comps = _components(bm)
    boxes = []
    for vs in comps:
        cmn = [1e18, 1e18, 1e18]; cmx = [-1e18, -1e18, -1e18]
        for v in vs:
            w = mw @ v.co
            for i in range(3):
                cmn[i] = min(cmn[i], w[i]); cmx[i] = max(cmx[i], w[i])
        boxes.append((cmn, cmx))
    bm.free()

    # Merge islands whose bboxes overlap (tolerance scaled to object size).
    tol = max(0.01, 0.02 * max(dims))
    m = len(boxes)
    gp = list(range(m))
    def gfind(x):
        while gp[x] != x:
            gp[x] = gp[gp[x]]; x = gp[x]
        return x
    for i in range(m):
        for j in range(i + 1, m):
            a, b = boxes[i], boxes[j]
            if all(a[0][k] - tol <= b[1][k] and b[0][k] - tol <= a[1][k] for k in range(3)):
                ra, rb = gfind(i), gfind(j)
                if ra != rb:
                    gp[ra] = rb
    scatter_groups = len(set(gfind(i) for i in range(m))) if m else 0

    out.append({"name": o.name, "dims_m": [round(d, 4) for d in dims],
                "longest_dim_m": round(max(dims), 4), "lowest_z_m": round(mn[2], 4),
                "island_count": m, "scatter_groups": scatter_groups,
                "has_geometry": True})

print("@@AUDIT_START@@" + json.dumps(out) + "@@AUDIT_END@@")
"""


def _measure() -> list[ObjectAudit]:
    """Run the bpy measurement script and parse the per-object results."""
    raw = blender_io.run_code(_AUDIT_CODE, timeout=120.0)
    start, end = raw.find("@@AUDIT_START@@"), raw.find("@@AUDIT_END@@")
    if start == -1 or end == -1:
        raise blender_io.BlenderError(f"geometry audit produced no data (output: {raw!r})")
    payload = raw[start + len("@@AUDIT_START@@"):end]
    return [ObjectAudit(**d) for d in json.loads(payload)]


def audit_scene(spec: BuildSpec, size_targets: dict[str, float] | None = None) -> GeometryAudit:
    """Measure the live scene and compare it against the plan.

    `size_targets` overrides per-object target longest-dimension in meters (e.g.
    real dimensions pulled from the web by the reference agent); falls back to each
    ObjectBrief's approx_size_m. Returns a GeometryAudit whose `problems` are
    concrete builder instructions and whose `ok` is True when none were found.
    """
    objects = _measure()
    by_name = {o.name: o for o in objects}
    problems: list[str] = []
    size_targets = size_targets or {}

    for brief in spec.objects:
        target = size_targets.get(brief.name, brief.approx_size_m)
        match = by_name.get(brief.name)
        # Builders don't always name the object exactly; fall back to a single
        # built object when the plan has a single object too.
        if match is None and len(objects) == 1 and len(spec.objects) == 1:
            match = objects[0]
        if match is None:
            problems.append(
                f"object '{brief.name}' ({brief.description}) is MISSING from the "
                f"scene — model it."
            )
            continue
        if not match.has_geometry:
            problems.append(f"object '{match.name}' has no geometry — re-model it.")
            continue
        if match.scatter_groups > 1:
            problems.append(
                f"object '{match.name}' has {match.scatter_groups} parts floating "
                f"apart (not connected) — move/overlap them so all parts touch and "
                f"join into one solid object."
            )
        if target > 0 and match.longest_dim_m > 0:
            ratio = match.longest_dim_m / target
            if ratio > _SIZE_TOLERANCE or ratio < 1.0 / _SIZE_TOLERANCE:
                problems.append(
                    f"object '{match.name}' is mis-sized: longest dimension is "
                    f"{match.longest_dim_m:.2f} m but target is {target:.2f} m — "
                    f"scale it by ~{1.0 / ratio:.2f}x."
                )

    return GeometryAudit(ok=not problems, objects=objects, problems=problems)
