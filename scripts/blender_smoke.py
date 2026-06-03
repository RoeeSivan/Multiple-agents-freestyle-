"""End-to-end smoke test of the Blender geometry backend (no LLM, no SMS).

Clears the scene, generates one real mesh via Hyper3D Rodin, screenshots the
viewport, and exports a game-ready .glb — exercising the exact `blender_io`
calls the pipeline uses. Run with Blender open + the BlenderMCP addon connected
(Rodin + PolyHaven enabled):

    uv run python -m scripts.blender_smoke "a red sports car"
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from app.config import OUT_DIR
from app.rendering import blender_io as bio


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "a red sports car"

    if not bio.reachable():
        print("FAIL: Blender addon not reachable on the configured port.")
        return 1
    h = bio.hyper3d_status()
    if not h.get("enabled"):
        print(f"FAIL: Hyper3D Rodin is disabled: {h.get('message')}")
        return 1
    print(f"Rodin OK ({h.get('message', '')[:60]}). Building: {prompt!r}")

    out = OUT_DIR / "smoke"
    out.mkdir(parents=True, exist_ok=True)
    png, glb = out / "smoke.png", out / "smoke.glb"

    t0 = time.time()
    bio.clear_scene()
    info = bio.generate_object(name="smoke_obj", description=prompt, target_size_m=2.0)
    print(f"  generated + imported in {time.time() - t0:.0f}s: {info.get('name')}")

    bio.render_png(png)
    bio.export_glb(glb)

    png_kb = png.stat().st_size / 1024 if png.exists() else 0
    glb_kb = glb.stat().st_size / 1024 if glb.exists() else 0
    print(f"  png: {png_kb:.0f} KB  ->  {png}")
    print(f"  glb: {glb_kb:.0f} KB  ->  {glb}")

    if glb_kb < 20:
        print("FAIL: glb suspiciously small — mesh probably did not import.")
        return 1
    print(f"PASS in {time.time() - t0:.0f}s total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
