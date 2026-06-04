"""Smoke-test the USER-PHOTO build path (no SMS, no upload server).

Exercises the exact plumbing the upload flow uses: PlannerAgent -> ViewPlanner
(plan_views) -> reference_from_photos(user photos) -> build_3d(spec, references)
-> PNG + GLB. Photos-only grounding: the photographed object is NOT web-fetched.

Pass a folder of real photos (front/back/side ...) for a meaningful result; with
no folder it generates solid-color placeholders so the pipeline itself is still
exercised end-to-end. Needs Blender open with the BlenderMCP addon + OPENAI_API_KEY.

    uv run python -m scripts.photo_intake_smoke "a wooden chair" ~/Desktop/chair_photos
    uv run python -m scripts.photo_intake_smoke "a wooden chair"   # placeholder photos
"""
from __future__ import annotations

import asyncio
import struct
import sys
import time
import zlib
from pathlib import Path

from app.agents import build_spec, plan_views, reference_from_photos
from app.config import OUT_DIR
from app.pipeline import build_3d
from app.rendering import blender_io as bio
from app.state import ObjectIntake

_VIEWS = ["front", "back", "side", "top"]
_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def _solid_png(path: Path, rgb: tuple[int, int, int], size: int = 128) -> None:
    """Write a small solid-color PNG using only the stdlib (no Pillow dep)."""
    row = bytes((0,)) + bytes(rgb) * size  # filter byte 0 + RGB pixels
    raw = row * size

    def chunk(typ: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + typ + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit RGB
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def _collect_photos(obj_name: str, photos_dir: Path | None, out_dir: Path) -> dict[str, str]:
    """Map up to 4 photos to views. Real folder if given, else placeholders."""
    dest = out_dir / "userphotos" / obj_name
    dest.mkdir(parents=True, exist_ok=True)
    received: dict[str, str] = {}
    if photos_dir and photos_dir.is_dir():
        files = sorted(p for p in photos_dir.iterdir() if p.suffix.lower() in _IMG_EXTS)
        for view, src in zip(_VIEWS, files):
            received[view] = str(src)
    else:
        # Distinct solids so the run is deterministic (plumbing test, not accuracy).
        palette = {"front": (150, 95, 50), "back": (120, 78, 42), "side": (170, 110, 60)}
        for view, rgb in palette.items():
            p = dest / f"{view}.png"
            _solid_png(p, rgb)
            received[view] = str(p)
    return received


async def run(prompt: str, photos_dir: Path | None) -> int:
    if not bio.reachable():
        print("FAIL: Blender addon not reachable on the configured port.")
        return 1
    out_dir = OUT_DIR / "photo_smoke"
    print(f"Planning: {prompt!r}")
    t0 = time.time()

    spec = await build_spec(prompt)
    obj = spec.objects[0]
    print(f"  plan: {spec.title} -> objects {[o.name for o in spec.objects]}")

    plan = await plan_views(spec)
    for ov in plan.objects:
        tag = f"views={ov.views}" if ov.needs_photos else "no photos (web is enough)"
        print(f"  view-plan[{ov.object_name}]: needs_photos={ov.needs_photos}  {tag}")

    received = _collect_photos(obj.name, photos_dir, out_dir)
    intake_obj = ObjectIntake(
        name=obj.name,
        label=obj.name.replace("_", " "),
        views=list(received.keys()),
        prompts={v: "" for v in received},
        received=received,
    )
    ref = reference_from_photos(intake_obj)
    print(f"  grounding {obj.name!r} on {len(ref.images)} user photo(s): {ref.image_labels}")

    res = await build_3d(
        prompt,
        spec=spec,
        references={obj.name: ref},
        out_dir=out_dir,
        basename="photo_smoke",
        refine=False,
        turntable=False,
    )

    png_kb = res.png.stat().st_size / 1024 if res.png.exists() else 0
    glb_kb = res.glb.stat().st_size / 1024 if res.glb.exists() else 0
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
    photos_dir = Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else None
    return asyncio.run(run(prompt, photos_dir))


if __name__ == "__main__":
    raise SystemExit(main())
