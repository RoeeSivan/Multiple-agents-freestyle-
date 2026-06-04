"""Tuning driver — runs the FULL refine loop and dumps everything you need to
learn what to fine-tune.

Unlike `scripts.blender_smoke` (critic loop OFF, for a fast pass/fail), this runs
the real build with `refine=True` so the audit + multi-view critic actually fire,
then prints the plan, the web references, the per-pass trace (what each refine pass
measured + what the critic said), convergence, and file/triangle stats. The 5 view
renders + hero PNG are left in the out dir so you can eyeball them. Needs Blender
open with the BlenderMCP addon connected, plus OPENAI_API_KEY.

    uv run python -m scripts.tune_run "a park bench" bench
"""
from __future__ import annotations

import asyncio
import re
import sys
import time
from pathlib import Path

from app.config import OUT_DIR
from app.pipeline import build_3d
from app.rendering import blender_io as bio

# Evaluated-mesh triangle count of the LIVE scene (incl. modifiers) — a proxy for
# the exported .glb's weight. Run right after the build, while the scene is live.
_TRIS_CODE = """
import bpy
dg = bpy.context.evaluated_depsgraph_get()
tris = 0
for o in bpy.data.objects:
    if o.type != 'MESH':
        continue
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    me.calc_loop_triangles()
    tris += len(me.loop_triangles)
    ev.to_mesh_clear()
print("@@TRIS@@" + str(tris) + "@@")
"""


def _slug(prompt: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", prompt.lower()).strip("_")
    return s[:40] or "object"


def _tri_count() -> int | None:
    try:
        raw = bio.run_code(_TRIS_CODE, timeout=120.0)
        m = re.search(r"@@TRIS@@(\d+)@@", raw)
        return int(m.group(1)) if m else None
    except Exception:  # noqa: BLE001 — diagnostic only
        return None


async def run(prompt: str, slug: str) -> int:
    if not bio.reachable():
        print("FAIL: Blender addon not reachable on the configured port.")
        return 1

    out = OUT_DIR / "tune" / slug
    print(f"Tuning run: {prompt!r}  (full refine loop ON) -> {out}")
    t0 = time.time()
    res = await build_3d(prompt, out_dir=out, basename="m", refine=True, turntable=False)
    dt = time.time() - t0

    # ---- plan -------------------------------------------------------------
    print(f"\n=== PLAN: {res.spec.title} ===")
    print(f"environment={res.spec.environment!r}  camera={res.spec.camera_hint!r}")
    for o in res.spec.objects:
        print(f"\n  • {o.name}  (~{o.approx_size_m} m)  pos={o.position_hint!r}")
        print(f"    desc: {o.description}")
        if o.proportions:
            print(f"    proportions: {o.proportions}")
        if o.symmetry:
            print(f"    symmetry: {o.symmetry}")
        if o.material_hint:
            print(f"    material: {o.material_hint}")
        for p in o.parts:
            dims = "x".join(f"{d:g}" for d in p.approx_dims_m) if p.approx_dims_m else "?"
            print(f"      - {p.name}: {p.shape_hint or '?'}  [{dims} m]  anchor={p.anchor!r}")

    # ---- references -------------------------------------------------------
    print("\n=== REFERENCES (web/photo grounding) ===")
    for name, ref in (res.references or {}).items():
        if ref is None:
            print(f"  • {name}: (none)")
            continue
        print(f"  • {name}: real_dims={ref.real_dims_m} m  imgs={len(ref.images)}")
        if ref.facts:
            print(f"      facts: {ref.facts[:200]}")

    # ---- per-pass trace --------------------------------------------------
    print("\n=== REFINE TRACE (per pass) ===")
    if not res.trace:
        print("  (no refine passes recorded)")
    for t in res.trace:
        print(f"  iter {t['iter']}: audit_ok={t['audit_ok']}  "
              f"critic_match={t['critic_match']}")
        for prob in t["audit_problems"]:
            print(f"      audit: {prob}")
        if t["critic_notes"]:
            print(f"      critic: {t['critic_notes']}")

    # ---- outcome ---------------------------------------------------------
    converged = bool(res.critique and res.critique.matches_request
                     and res.audit and res.audit.ok)
    png_kb = res.png.stat().st_size / 1024 if res.png.exists() else 0
    glb_kb = res.glb.stat().st_size / 1024 if res.glb.exists() else 0
    tris = _tri_count()
    print("\n=== OUTCOME ===")
    print(f"  converged={converged}  iterations={res.iterations}  time={dt:.0f}s")
    print(f"  png={png_kb:.0f} KB  glb={glb_kb:.0f} KB  tris={tris}")
    print(f"  views to inspect: {out}/view_*.png  hero: {res.png}")
    print(f"  trace: {out}/trace.json")

    if glb_kb < 5:
        print("\nFAIL: glb suspiciously small — modeling probably produced nothing.")
        return 1
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: python -m scripts.tune_run "<description>" [slug]')
        return 2
    prompt = sys.argv[1]
    slug = sys.argv[2] if len(sys.argv) > 2 else _slug(prompt)
    return asyncio.run(run(prompt, slug))


if __name__ == "__main__":
    raise SystemExit(main())
