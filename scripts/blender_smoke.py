"""End-to-end smoke test of the agentic-modeling backend (no SMS).

Runs the real pipeline once with the critic loop OFF: PlannerAgent turns the
prompt into a BuildSpec, the BuilderAgent MODELS it in the live Blender via the
blender-mcp toolset, then we render a PNG and export a .glb. Exercises the exact
path the SMS server uses. Needs Blender open with the BlenderMCP addon connected,
plus OPENAI_API_KEY.

    uv run python -m scripts.blender_smoke "a wooden chair"
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

from app.config import OUT_DIR
from app.pipeline import build_3d
from app.rendering import blender_io as bio


async def run(prompt: str) -> int:
    if not bio.reachable():
        print("FAIL: Blender addon not reachable on the configured port.")
        return 1
    print(f"Modeling: {prompt!r}  (critic loop off for speed)")

    t0 = time.time()
    res = await build_3d(
        prompt, out_dir=OUT_DIR / "smoke", basename="smoke", refine=False
    )

    png_kb = res.png.stat().st_size / 1024 if res.png.exists() else 0
    glb_kb = res.glb.stat().st_size / 1024 if res.glb.exists() else 0
    print(f"  plan: {res.spec.title} -> objects {[o.name for o in res.spec.objects]}")
    print(f"  built: {res.report.objects_built}  ({res.report.notes[:80]})")
    print(f"  png: {png_kb:.0f} KB -> {res.png}")
    print(f"  glb: {glb_kb:.0f} KB -> {res.glb}")

    if glb_kb < 5:
        print("FAIL: glb suspiciously small — modeling probably produced nothing.")
        return 1
    print(f"PASS in {time.time() - t0:.0f}s.")
    return 0


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "a wooden chair"
    return asyncio.run(run(prompt))


if __name__ == "__main__":
    raise SystemExit(main())
