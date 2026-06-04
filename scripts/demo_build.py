"""Generate demo assets that SHOW the model evolving, for the walkthrough video.

Same multi-agent loop as `app.pipeline.build_3d`, but snapshots a hero render
AFTER EACH builder pass (`evo_1.png`, `evo_2.png`, ...) so the video can show the
model developing pass by pass — plus a final hero PNG, a turntable MP4, the .glb,
and a `demo.json` capturing the SMS-side narrative (plan title, object names,
per-pass critic notes). Needs Blender open with the BlenderMCP addon connected
and OPENAI_API_KEY.

    uv run python -m scripts.demo_build "a wooden chair"
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

from app.agents.builder import build_scene
from app.agents.critic import critique_render
from app.agents.intent import build_spec
from app.agents.reference import get_reference
from app.config import OUT_DIR, settings
from app.rendering import blender_io as bio
from app.rendering.geometry_audit import audit_scene


async def run(prompt: str, out_name: str = "demo_chair") -> int:
    if not bio.reachable():
        print("FAIL: Blender addon not reachable on :9876.")
        return 1

    out_dir = OUT_DIR / out_name
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    print(f"Demo build: {prompt!r} -> {out_dir}")

    # 1. plan (no Blender)
    spec = await build_spec(prompt)
    print(f"  plan: {spec.title} -> {[o.name for o in spec.objects]}")

    # 2. web reference per object (no Blender, concurrent)
    refs: dict = {}
    if settings.web_reference:
        results = await asyncio.gather(*[get_reference(b, out_dir) for b in spec.objects])
        refs = {b.name: r for b, r in zip(spec.objects, results)}
    size_targets = {n: r.real_dims_m for n, r in refs.items() if r and r.real_dims_m > 0}

    # 3. build loop with per-pass snapshots
    bio.clear_scene()
    evo: list[dict] = []  # one entry per pass: {png, audit_problems, critic_notes, ...}

    report = await build_scene(spec, is_edit=False, references=refs)
    snap = out_dir / "evo_1.png"
    await asyncio.to_thread(bio.render_png, snap)
    print(f"  pass 1 built -> {snap.name}")

    max_iter = settings.max_iterations
    iterations = 1
    audit = await asyncio.to_thread(audit_scene, spec, size_targets)
    views = await asyncio.to_thread(bio.render_views, out_dir)
    while iterations < max_iter:
        critique = await critique_render(prompt, spec, views, refs)
        evo.append({
            "pass": iterations,
            "png": f"evo_{iterations}.png",
            "audit_ok": audit.ok,
            "audit_problems": list(audit.problems),
            "critic_match": critique.matches_request,
            "critic_notes": critique.patch_instructions,
            "critic_issues": list(critique.issues),
        })
        print(f"  pass {iterations}: audit_ok={audit.ok} critic_match={critique.matches_request}")
        if critique.matches_request and audit.ok:
            break
        feedback_parts = []
        if audit.problems:
            feedback_parts.append("MEASURED geometry problems:\n- " + "\n- ".join(audit.problems))
        if critique.patch_instructions:
            feedback_parts.append("VISUAL review notes:\n" + critique.patch_instructions)
        feedback = "\n\n".join(feedback_parts)
        if not feedback:
            break
        report = await build_scene(spec, feedback=feedback)
        iterations += 1
        snap = out_dir / f"evo_{iterations}.png"
        await asyncio.to_thread(bio.render_png, snap)
        audit = await asyncio.to_thread(audit_scene, spec, size_targets)
        views = await asyncio.to_thread(bio.render_views, out_dir)
        print(f"  pass {iterations} built -> {snap.name}")

    # 4. final hero + glb + turntable
    png_path = out_dir / f"{out_name}.png"
    glb_path = out_dir / f"{out_name}.glb"
    mp4_path = out_dir / f"{out_name}.mp4"
    await asyncio.to_thread(bio.render_png, png_path)
    await asyncio.to_thread(bio.export_glb, glb_path)
    mp4 = None
    try:
        mp4 = await asyncio.to_thread(bio.render_turntable, mp4_path)
    except Exception as e:  # noqa: BLE001
        print(f"  turntable failed: {e}")

    demo = {
        "prompt": prompt,
        "title": spec.title,
        "objects": [o.name for o in spec.objects],
        "facts": next((r.facts for r in refs.values() if r and r.facts), [])[:3],
        "passes": evo,
        "final_png": png_path.name,
        "glb": glb_path.name,
        "mp4": Path(mp4).name if mp4 else None,
        "iterations": iterations,
        "seconds": round(time.time() - t0, 1),
    }
    (out_dir / "demo.json").write_text(json.dumps(demo, indent=2))
    print(f"PASS in {demo['seconds']}s. evo frames: {iterations}, mp4: {demo['mp4']}")
    print(f"  demo.json -> {out_dir / 'demo.json'}")
    return 0


def main() -> int:
    prompt = sys.argv[1] if len(sys.argv) > 1 else "a wooden chair"
    return asyncio.run(run(prompt))


if __name__ == "__main__":
    raise SystemExit(main())
