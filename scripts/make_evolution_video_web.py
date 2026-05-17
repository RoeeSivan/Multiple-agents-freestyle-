"""
Evolution video using the REAL Three.js game (with the actual neon cars).

For each milestone genome:
  1. Materialise weights into a temporary .keras file.
  2. Spawn the local server + headed/headless Chromium via web_driver.drive.
  3. Record gameplay clip via Playwright video.
  4. Capture an audio event log from the page (audio.js _log hook).

Then concatenates a title card + every clip into one MP4 using ffmpeg's
concat filter, synthesises a single audio track from the captured event
logs (via viz/audio_synth.py), and muxes the audio into the final MP4.

Usage:
  python scripts/make_evolution_video_web.py \
      --output evolution_web.mp4 \
      --max-duration 30 \
      --include-final \
      --headless

  # Subset of generations (faster):
  python scripts/make_evolution_video_web.py \
      --gens 10,40,70,80 --include-final --output evolution_web.mp4

  # Silent fallback (legacy behaviour):
  python scripts/make_evolution_video_web.py --no-audio --output ev.mp4
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Allow `python scripts/make_evolution_video_web.py` from project root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Must precede any `import keras`.
os.environ.setdefault("KERAS_BACKEND", "numpy")

import numpy as np


VIDEO_W = 1280
VIDEO_H = 800
TITLE_CARD_SECONDS = 1.5
INTRO_SECONDS = 5.0
OUTRO_SECONDS = 6.0
CHART_SECONDS = 20.0
FPS = 30  # output fps after re-encode


def _load_gen_stats(csv_path: Path) -> dict:
    """Map generation number -> per-gen stats dict from training.csv."""
    import csv as _csv
    out: dict = {}
    with csv_path.open() as fh:
        for row in _csv.DictReader(fh):
            try:
                gen = int(float(row["generation"]))
            except (KeyError, ValueError):
                continue
            out[gen] = {
                "best": float(row["best"]),
                "mean": float(row["mean"]),
                "median": float(row["median"]),
                "worst": float(row["worst"]),
                "best_score": float(row["best_score"]),
                "best_level": int(float(row["best_level"])),
                "best_frames": int(float(row["best_frames"])),
                "elapsed_s": float(row["elapsed_s"]),
            }
    return out


def _font(size: int):
    from PIL import ImageFont
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


def _write_still(img, out_path: Path, seconds: float) -> None:
    """Encode a PIL image as a constant-frame MP4 of the requested length."""
    import imageio.v2 as imageio  # type: ignore
    arr = np.array(img)
    n = int(seconds * FPS)
    writer = imageio.get_writer(
        str(out_path), fps=FPS, codec="libx264", quality=8, macro_block_size=1,
    )
    try:
        for _ in range(n):
            writer.append_data(arr)
    finally:
        writer.close()


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


def _make_title_card(
    label: str,
    sub: str,
    out_path: Path,
    extra_line: Optional[str] = None,
) -> None:
    """Generate a short MP4 title card via imageio."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (VIDEO_W, VIDEO_H), (10, 10, 20))
    draw = ImageDraw.Draw(img)

    big = _font(96)
    small = _font(40)
    stat = _font(48)
    bbox = draw.textbbox((0, 0), label, font=big)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    cy = VIDEO_H / 2 - (0 if not extra_line else 40)
    draw.text(((VIDEO_W - w) / 2, cy - h / 2 - 30),
              label, fill=(240, 240, 255), font=big)
    bbox2 = draw.textbbox((0, 0), sub, font=small)
    w2 = bbox2[2] - bbox2[0]
    draw.text(((VIDEO_W - w2) / 2, cy + h / 2 + 30),
              sub, fill=(160, 160, 200), font=small)
    if extra_line:
        bbox3 = draw.textbbox((0, 0), extra_line, font=stat)
        w3 = bbox3[2] - bbox3[0]
        draw.text(((VIDEO_W - w3) / 2, cy + h / 2 + 100),
                  extra_line, fill=(0, 255, 170), font=stat)

    _write_still(img, out_path, TITLE_CARD_SECONDS)


def _make_intro_card(out_path: Path, seconds: float = INTRO_SECONDS) -> None:
    """Multi-section opener: problem statement + NN/GA setup."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (VIDEO_W, VIDEO_H), (10, 10, 22))
    draw = ImageDraw.Draw(img)

    title = "Neon Highway"
    subtitle = "Keras Neural Network · evolved by Genetic Algorithm"

    f_title = _font(108)
    f_sub = _font(38)
    f_body = _font(28)
    f_section = _font(30)

    bbox = draw.textbbox((0, 0), title, font=f_title)
    w = bbox[2] - bbox[0]
    draw.text(((VIDEO_W - w) / 2, 70), title,
              fill=(0, 255, 170), font=f_title)

    bbox = draw.textbbox((0, 0), subtitle, font=f_sub)
    w = bbox[2] - bbox[0]
    draw.text(((VIDEO_W - w) / 2, 210), subtitle,
              fill=(180, 180, 220), font=f_sub)

    left_x = 90
    right_x = 690
    body_y = 320

    def _block(x: int, y: int, header: str, lines: List[str], header_color):
        draw.text((x, y), header, fill=header_color, font=f_section)
        for i, line in enumerate(lines):
            draw.text((x, y + 60 + i * 42),
                      "• " + line, fill=(220, 220, 235), font=f_body)

    _block(left_x, body_y, "Problem", [
        "Pilot a car on an obstacle highway.",
        "No supervised dataset.",
        "Stay alive, score, reach max level.",
    ], header_color=(255, 170, 0))

    _block(right_x, body_y, "Approach", [
        "MLP 16-24-16-4 (Keras numpy).",
        "Pop 60 · tournament + elitism.",
        "Fitness = survival + score + level.",
    ], header_color=(170, 136, 255))

    footer = "Press play — the chart shows fitness improving across 81 generations."
    bbox = draw.textbbox((0, 0), footer, font=f_body)
    w = bbox[2] - bbox[0]
    draw.text(((VIDEO_W - w) / 2, VIDEO_H - 60),
              footer, fill=(140, 200, 255), font=f_body)

    _write_still(img, out_path, seconds)


def _make_outro_card(
    out_path: Path, seconds: float = OUTRO_SECONDS,
    stats: Optional[dict] = None,
) -> None:
    """Final card — championship stats + saved-weights artefact."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (VIDEO_W, VIDEO_H), (10, 10, 22))
    draw = ImageDraw.Draw(img)

    f_title = _font(96)
    f_stat = _font(40)
    f_path = _font(32)

    title = "Final Champion"
    bbox = draw.textbbox((0, 0), title, font=f_title)
    w = bbox[2] - bbox[0]
    draw.text(((VIDEO_W - w) / 2, 90),
              title, fill=(0, 255, 170), font=f_title)

    stats = stats or {}
    best_fit = stats.get("best", 49980)
    best_score = stats.get("best_score", 48750)
    best_level = stats.get("best_level", 6)
    best_frames = stats.get("best_frames", 9802)
    surv_s = best_frames / 60.0

    lines = [
        f"Best fitness:    {best_fit:>10,.0f}",
        f"Raw score:       {best_score:>10,.0f}",
        f"Level reached:   {best_level} / 6   (max difficulty)",
        f"Survival:        {best_frames:,} frames  (~{surv_s:.0f} s)",
        f"Wall-clock:      ~75 min   ·   60 pop   ·   81 gens",
    ]
    y0 = 250
    for i, line in enumerate(lines):
        draw.text((220, y0 + i * 58), line,
                  fill=(220, 220, 235), font=f_stat)

    saved_label = "Weights saved:"
    saved_path = "checkpoints/best.keras"
    bbox = draw.textbbox((0, 0), saved_label, font=f_stat)
    draw.text((220, VIDEO_H - 130),
              saved_label, fill=(170, 136, 255), font=f_stat)
    draw.text((220 + bbox[2] + 20, VIDEO_H - 128),
              saved_path, fill=(0, 255, 170), font=f_path)

    _write_still(img, out_path, seconds)


def _make_chart_segment(
    csv_path: Path, out_path: Path, seconds: float = CHART_SECONDS,
) -> None:
    """Render animated fitness chart by reusing make_chart_animation.render()."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from make_chart_animation import render as _render_chart  # type: ignore
    finally:
        sys.path.pop(0)
    _render_chart(csv_path, out_path, duration_s=seconds, fps=FPS)


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


def _probe_duration(path: Path) -> float:
    """Return container duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


def _build_audio_track(
    entries: List[dict],
    total_duration_s: float,
    out_wav: Path,
) -> None:
    """Synth a single WAV from the global event timeline.

    `entries` is a list of {t: seconds, type: str, freq?: float}.
    """
    from viz import audio_synth as A

    mixer = A.Mixer(duration_s=total_duration_s + 1.0)
    for e in entries:
        t = float(e["t"])
        et = e["type"]
        if et == "melody":
            freq = float(e.get("freq", 440.0))
            mixer.add(t, A.synth_melody_note(freq))
        elif et == "collision":
            mixer.add(t, A.synth_collision())
        elif et == "coin":
            mixer.add(t, A.synth_coin())
        elif et == "laser_hit":
            mixer.add(t, A.synth_laser_hit())
        elif et == "laser_shoot":
            mixer.add(t, A.synth_laser_shoot())
        elif et == "warp":
            mixer.add(t, A.synth_warp())
    mixer.to_wav(out_wav)


def _mux_audio(silent_mp4: Path, wav: Path, out: Path) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-i", str(silent_mp4),
        "-i", str(wav),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(out),
    ]
    print(f"[mux] {' '.join(cmd[:6])} ... {out}")
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
    ap.add_argument("--no-audio", action="store_true",
                    help="Skip audio capture/synthesis (silent output).")
    ap.add_argument("--intro", action="store_true",
                    help="Prepend intro card explaining problem + NN/GA setup.")
    ap.add_argument("--outro", action="store_true",
                    help="Append outro card with final stats + saved-weights path.")
    ap.add_argument("--chart-segment", action="store_true",
                    help="Prepend animated fitness chart from --training-csv.")
    ap.add_argument("--training-csv", default="training_run_2026-05-14/training.csv",
                    help="training.csv used for chart animation and title-card stats.")
    ap.add_argument("--reuse-clips", action="store_true",
                    help="Skip Playwright if clip_XX.webm + events JSON already exist in tmp.")
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

    # Per-gen stats keyed by generation number, used both for enhanced
    # title cards and the outro stat block.
    csv_path = Path(args.training_csv)
    gen_stats: dict = _load_gen_stats(csv_path) if csv_path.exists() else {}
    if csv_path.exists() and not gen_stats:
        print(f"  ⚠ training csv had no rows: {csv_path}")

    drive_web = None  # lazy import only if we're actually driving
    if not args.reuse_clips:
        from web_driver.drive import drive_web as _dw
        drive_web = _dw

    # Track each timeline item: ("title", path) or ("clip", path, events_path).
    timeline: List[tuple] = []
    for idx, (label, src_path, gen_num) in enumerate(ckpts):
        print(f"\n[{idx + 1}/{len(ckpts)}] {label}")

        # Pull stats for this gen so the title card can show "Best fitness: …".
        stats = gen_stats.get(gen_num) if gen_num is not None else None
        if stats is None and gen_num is None and gen_stats:
            # "Final Champion" — show the overall best fitness across the run.
            best_gen = max(gen_stats, key=lambda g: gen_stats[g]["best"])
            stats = gen_stats[best_gen]
        extra = (f"Best fitness: {stats['best']:,.0f}"
                 if stats is not None else None)

        title_mp4 = titles_dir / f"title_{idx:02d}.mp4"
        _make_title_card(
            label,
            "Neon Highway · GA evolution",
            title_mp4,
            extra_line=extra,
        )
        timeline.append(("title", title_mp4))

        clip_path = clips_dir / f"clip_{idx:02d}.webm"
        events_path = clips_dir / f"clip_{idx:02d}.events.json"

        if args.reuse_clips and clip_path.exists():
            print(f"  ↻ reusing existing clip {clip_path.name}")
        else:
            if drive_web is None:
                print(f"  ⚠ --reuse-clips set but {clip_path} missing — skipping")
                continue
            keras_tmp = tmp / f"genome_{idx:02d}.keras"
            _materialise_keras(src_path, keras_tmp)
            drive_web(
                genome_path=str(keras_tmp),
                port=args.port + idx,  # each spawns a server; avoid reuse
                record_path=str(clip_path),
                max_duration_s=args.max_duration,
                headless=args.headless,
                web_game_dir="web_game",
                events_path=str(events_path),
                capture_audio_events=not args.no_audio,
            )
            if not clip_path.exists():
                print(f"  ⚠ clip missing — skipping")
                continue
        timeline.append(("clip", clip_path, events_path))

    # Optional intro/chart/outro segments wrap the per-gen timeline.
    intro_path: Optional[Path] = None
    chart_path: Optional[Path] = None
    outro_path: Optional[Path] = None
    if args.intro:
        intro_path = tmp / "intro.mp4"
        print(f"\n[intro] rendering → {intro_path}")
        _make_intro_card(intro_path)
    if args.chart_segment:
        if not csv_path.exists():
            raise SystemExit(f"--chart-segment needs --training-csv; not found: {csv_path}")
        chart_path = tmp / "chart.mp4"
        print(f"[chart] rendering animated fitness chart → {chart_path}")
        _make_chart_segment(csv_path, chart_path)
    if args.outro:
        outro_path = tmp / "outro.mp4"
        # Pick the gen with the highest fitness for the outro summary.
        outro_stats = None
        if gen_stats:
            best_gen = max(gen_stats, key=lambda g: gen_stats[g]["best"])
            outro_stats = gen_stats[best_gen]
        print(f"[outro] rendering → {outro_path}")
        _make_outro_card(outro_path, stats=outro_stats)

    # Build the list of paths for the visual concat (silent).
    visual_inputs: List[Path] = []
    if intro_path is not None:
        visual_inputs.append(intro_path)
    if chart_path is not None:
        visual_inputs.append(chart_path)
    visual_inputs.extend(item[1] for item in timeline)
    if outro_path is not None:
        visual_inputs.append(outro_path)

    if args.no_audio:
        print("\n[concat] merging clips + title cards (silent)")
        _ffmpeg_concat(visual_inputs, Path(args.output))
    else:
        silent_mp4 = tmp / "silent.mp4"
        print("\n[concat] merging clips + title cards → silent.mp4")
        _ffmpeg_concat(visual_inputs, silent_mp4)

        print("[audio] aggregating events from clips")
        global_entries: List[dict] = []
        # Skip silent prefix: intro card + chart animation segment, in that
        # order. Outro is the final silent suffix and contributes nothing.
        prefix_s = 0.0
        if intro_path is not None:
            prefix_s += INTRO_SECONDS
        if chart_path is not None:
            prefix_s += CHART_SECONDS
        cursor_s = prefix_s
        for item in timeline:
            kind = item[0]
            if kind == "title":
                cursor_s += TITLE_CARD_SECONDS
                continue
            _, clip_path, events_path = item
            try:
                clip_dur = _probe_duration(clip_path)
            except Exception as e:
                print(f"  ⚠ probe failed on {clip_path}: {e}; skipping its audio")
                cursor_s += args.max_duration
                continue
            if events_path.exists():
                try:
                    events = json.loads(events_path.read_text())
                except Exception as e:
                    print(f"  ⚠ bad events json {events_path}: {e}")
                    events = []
            else:
                events = []
            for ev in events:
                t_s = cursor_s + float(ev.get("t", 0.0)) / 1000.0
                # Drop events that fall past the clip's recorded duration —
                # they can happen if audio fires during ctx.close() flush.
                if t_s > cursor_s + clip_dur:
                    continue
                entry = {"t": t_s, "type": ev["type"]}
                if "freq" in ev:
                    entry["freq"] = ev["freq"]
                global_entries.append(entry)
            cursor_s += clip_dur

        wav_path = tmp / "track.wav"
        print(f"[audio] synthesising {len(global_entries)} events → {wav_path}")
        _build_audio_track(global_entries, total_duration_s=cursor_s, out_wav=wav_path)

        print(f"[audio] muxing → {args.output}")
        _mux_audio(silent_mp4, wav_path, Path(args.output))

    print(f"\n✓ wrote {args.output}")

    if not args.keep_clips:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
