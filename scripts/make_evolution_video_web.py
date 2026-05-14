"""
Evolution video using the REAL Three.js game (with the actual neon cars).

For each milestone genome:
  1. Materialise weights into a temporary .keras file.
  2. Spawn the local server + headed/headless Chromium via web_driver.drive.
  3. Record gameplay clip via Playwright video.

Then concatenates a title card + every clip into one MP4 using ffmpeg's
concat filter (handles mixed codec/container by re-encoding).

Usage:
  python scripts/make_evolution_video_web.py \
      --output evolution_web.mp4 \
      --max-duration 30 \
      --include-final \
      --headless

  # Subset of generations (faster):
  python scripts/make_evolution_video_web.py \
      --gens 10,40,70,80 --include-final --output evolution_web.mp4
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# Must precede any `import keras`.
os.environ.setdefault("KERAS_BACKEND", "numpy")

import numpy as np


VIDEO_W = 1280
VIDEO_H = 800
TITLE_CARD_SECONDS = 1.5
FPS = 30  # output fps after re-encode


def _gather_checkpoints(
    ckpt_dir: Path,
    gens_filter: Optional[List[int]],
    include_final: bool,
) -> List[Tuple[str, Path, Optional[int]]]:
    """Return list of (label, keras_path, gen_number)."""
    pat = re.compile(r"best_gen(\d+)\.npz$")
    found: List[Tuple[int, Path]] = []
    for p in ckpt_dir.iterdir():
        m = pat.search(p.name)
        if m:
            found.append((int(m.group(1)), p))
    found.sort(key=lambda t: t[0])

    if gens_filter is not None:
        wanted = set(gens_filter)
        found = [(g, p) for g, p in found if g in wanted]

    out: List[Tuple[str, Path, Optional[int]]] = []
    for gen_num, path in found:
        out.append((f"Generation {gen_num}", path, gen_num))

    if include_final:
        final = ckpt_dir / "best.keras"
        if final.exists():
            out.append(("Final Champion", final, None))

    return out


def _materialise_keras(npz_or_keras: Path, dst: Path) -> Path:
    """Return path to a .keras file. Builds one from .npz if needed."""
    if npz_or_keras.suffix == ".keras":
        shutil.copy2(npz_or_keras, dst)
        return dst

    from nn.model import build_model, set_weights_into
    import keras  # noqa: F401  - ensures backend init order
    model = build_model()
    data = np.load(npz_or_keras)
    weights = [data[f"arr_{i}"] for i in range(len(data.files))]
    set_weights_into(model, weights)
    model.save(str(dst))
    return dst


def _make_title_card(label: str, sub: str, out_path: Path) -> None:
    """Generate a short MP4 title card via imageio."""
    import imageio.v2 as imageio  # type: ignore
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (VIDEO_W, VIDEO_H), (10, 10, 20))
    draw = ImageDraw.Draw(img)

    def _font(size: int) -> ImageFont.FreeTypeFont:
        for candidate in (
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNS.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ):
            if Path(candidate).exists():
                try:
                    return ImageFont.truetype(candidate, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    big = _font(96)
    small = _font(40)
    bbox = draw.textbbox((0, 0), label, font=big)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    draw.text(((VIDEO_W - w) / 2, (VIDEO_H - h) / 2 - 30),
              label, fill=(240, 240, 255), font=big)
    bbox2 = draw.textbbox((0, 0), sub, font=small)
    w2 = bbox2[2] - bbox2[0]
    draw.text(((VIDEO_W - w2) / 2, (VIDEO_H + h) / 2 + 30),
              sub, fill=(160, 160, 200), font=small)

    arr = np.array(img)
    n = int(TITLE_CARD_SECONDS * FPS)
    writer = imageio.get_writer(
        str(out_path), fps=FPS, codec="libx264", quality=8, macro_block_size=1,
    )
    try:
        for _ in range(n):
            writer.append_data(arr)
    finally:
        writer.close()


def _ffmpeg_concat(inputs: List[Path], output: Path) -> None:
    """Concat inputs via filter_complex (re-encode, handles mixed codecs)."""
    cmd: List[str] = ["ffmpeg", "-y"]
    for p in inputs:
        cmd += ["-i", str(p)]
    n = len(inputs)
    filter_arg = "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    cmd += [
        "-filter_complex", filter_arg,
        "-map", "[v]",
        "-c:v", "libx264",
        "-crf", "22",
        "-preset", "fast",
        "-pix_fmt", "yuv420p",
        str(output),
    ]
    print(f"[concat] {' '.join(cmd[:6])} ... {output}")
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="evolution_web.mp4")
    ap.add_argument("--checkpoints", default="checkpoints")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--max-duration", type=float, default=30.0,
                    help="Per-segment cap in seconds.")
    ap.add_argument("--gens", default=None,
                    help="Comma-separated gen numbers (e.g. 10,30,60). Default: all.")
    ap.add_argument("--include-final", action="store_true")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--keep-clips", action="store_true",
                    help="Don't delete intermediate per-segment clips.")
    ap.add_argument("--tmp-dir", default="_evolution_tmp")
    args = ap.parse_args()

    gens_filter = None
    if args.gens:
        gens_filter = [int(x) for x in args.gens.split(",") if x.strip()]

    tmp = Path(args.tmp_dir)
    tmp.mkdir(parents=True, exist_ok=True)
    clips_dir = tmp / "clips"
    clips_dir.mkdir(exist_ok=True)
    titles_dir = tmp / "titles"
    titles_dir.mkdir(exist_ok=True)

    ckpts = _gather_checkpoints(
        Path(args.checkpoints), gens_filter, args.include_final,
    )
    if not ckpts:
        raise SystemExit("No checkpoints matched.")
    print(f"[plan] {len(ckpts)} segments")
    for label, _, _ in ckpts:
        print(f"  · {label}")

    from web_driver.drive import drive_web

    timeline: List[Path] = []
    for idx, (label, src_path, gen_num) in enumerate(ckpts):
        print(f"\n[{idx + 1}/{len(ckpts)}] {label}")

        title_mp4 = titles_dir / f"title_{idx:02d}.mp4"
        _make_title_card(
            label,
            "Neon Highway · GA evolution",
            title_mp4,
        )
        timeline.append(title_mp4)

        keras_tmp = tmp / f"genome_{idx:02d}.keras"
        _materialise_keras(src_path, keras_tmp)

        clip_path = clips_dir / f"clip_{idx:02d}.webm"
        drive_web(
            genome_path=str(keras_tmp),
            port=args.port + idx,  # each spawns a server; avoid reuse
            record_path=str(clip_path),
            max_duration_s=args.max_duration,
            headless=args.headless,
            web_game_dir="web_game",
        )
        if not clip_path.exists():
            print(f"  ⚠ clip missing — skipping")
            continue
        timeline.append(clip_path)

    print("\n[concat] merging clips + title cards")
    _ffmpeg_concat(timeline, Path(args.output))
    print(f"\n✓ wrote {args.output}")

    if not args.keep_clips:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
