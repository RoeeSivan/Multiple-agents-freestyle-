"""
Build a single MP4 showing the agent's evolution across GA generations.

Iterates checkpoints/best_gen*.npz (plus final best.keras) in order. For
each genome: replays one game with a HUD overlay tagging the generation,
and writes the frames into a single shared MP4 writer. Optional title-card
frames separate clips so the viewer sees the gen number for ~1 second
before the gameplay starts.

By default the final MP4 carries the same procedural audio as the live
browser game (web_game/js/audio.js + cfg.js MELODIES). Pass --no-audio
to produce a silent video.

Usage:
  python scripts/make_evolution_video.py --record evolution.mp4
  python scripts/make_evolution_video.py --record evolution.mp4 --seed 42 \
      --max-frames 1200 --include-final
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

# Must precede any `import keras`.
os.environ.setdefault("KERAS_BACKEND", "numpy")

import numpy as np


def _list_gen_checkpoints(ckpt_dir: Path) -> List[Tuple[int, Path]]:
    pat = re.compile(r"best_gen(\d+)\.npz$")
    out: List[Tuple[int, Path]] = []
    for p in ckpt_dir.iterdir():
        m = pat.search(p.name)
        if m:
            out.append((int(m.group(1)), p))
    out.sort(key=lambda t: t[0])
    return out


def _load_weights_into(model, weights_path: Path) -> None:
    from nn.model import set_weights_into
    data = np.load(weights_path)
    weights = [data[f"arr_{i}"] for i in range(len(data.files))]
    set_weights_into(model, weights)


def _render_title_card(width: int, height: int, lines: List[str], hold_frames: int):
    """Return a list of identical RGB frames for the title card."""
    import pygame
    pygame.font.init()
    surf = pygame.Surface((width, height))
    surf.fill((10, 10, 20))
    font_big = pygame.font.SysFont("Consolas,Menlo,monospace", 56, bold=True)
    font_small = pygame.font.SysFont("Consolas,Menlo,monospace", 22)
    y = height // 2 - 60
    for i, line in enumerate(lines):
        f = font_big if i == 0 else font_small
        col = (240, 240, 255) if i == 0 else (180, 180, 200)
        text = f.render(line, True, col)
        surf.blit(text, (width // 2 - text.get_width() // 2, y))
        y += text.get_height() + 8
    arr = pygame.surfarray.array3d(surf).swapaxes(0, 1)
    return [arr] * hold_frames


def _build_audio_track(
    events: List[Tuple[int, str]],
    total_frames: int,
    fps: int,
    seed: int,
    out_wav: Path,
) -> None:
    """Synth procedural audio for the entire video timeline.

    Events are (global_frame_idx, type). 'green' walks the shuffled
    melody playlist (web_game/js/main.js:343-354 semantics). Other types
    map to the matching audio.js synth.
    """
    from viz import audio_synth as A
    from viz.melodies import MELODIES, shuffled_playlist

    duration_s = total_frames / fps + 1.0  # +1 s tail so last note's decay fits
    mixer = A.Mixer(duration_s=duration_s)

    playlist = shuffled_playlist(seed)
    song_idx = 0
    melody_idx = 0

    for frame_idx, ev in events:
        t = frame_idx / fps
        if ev == "green":
            notes = MELODIES[playlist[song_idx]]["notes"]
            freq = notes[melody_idx]
            mixer.add(t, A.synth_melody_note(float(freq)))
            melody_idx += 1
            if melody_idx >= len(notes):
                melody_idx = 0
                song_idx = (song_idx + 1) % len(playlist)
        elif ev == "coin":
            mixer.add(t, A.synth_coin())
        elif ev == "collision":
            mixer.add(t, A.synth_collision())
        elif ev == "laser_hit":
            mixer.add(t, A.synth_laser_hit())
        elif ev == "warp":
            mixer.add(t, A.synth_warp())

    mixer.to_wav(out_wav)


def _mux_audio_video(video_path: Path, wav_path: Path, out_path: Path) -> None:
    """Mux video stream + WAV into final MP4 via the bundled ffmpeg binary."""
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-i", str(video_path),
        "-i", str(wav_path),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def make_video(
    record_path: Path,
    ckpt_dir: Path,
    seed: int,
    max_frames: int,
    include_final: bool,
    title_card_seconds: float,
    with_audio: bool = True,
) -> None:
    from game import config as C
    from game.engine import NeonHighwayEnv
    from game.renderer import Renderer
    from nn.model import build_model, predict_action
    from nn.observe import observe

    import imageio.v2 as imageio  # type: ignore

    gens = _list_gen_checkpoints(ckpt_dir)
    if not gens:
        raise SystemExit(f"No best_gen*.npz files in {ckpt_dir}")

    segments: List[Tuple[str, Optional[Path], Optional[Path]]] = []
    for gen_num, path in gens:
        segments.append((f"Generation {gen_num}", path, None))

    final_keras = ckpt_dir / "best.keras"
    if include_final and final_keras.exists():
        segments.append(("Final Champion", None, final_keras))

    print(f"Building {len(segments)} segments → {record_path}")

    renderer = Renderer(title="Neon Highway · Evolution")
    width, height = renderer.screen.get_size()
    title_hold = max(1, int(title_card_seconds * C.FPS))

    # When adding audio, write the visual track to a temp path first, then
    # mux. Otherwise write directly to the final destination.
    if with_audio:
        tmp_dir = Path(tempfile.mkdtemp(prefix="evo_audio_"))
        video_path = tmp_dir / "video.mp4"
        wav_path = tmp_dir / "audio.wav"
    else:
        tmp_dir = None
        video_path = record_path
        wav_path = None

    writer = imageio.get_writer(
        str(video_path), fps=C.FPS, codec="libx264", quality=8,
        macro_block_size=1,
    )

    all_events: List[Tuple[int, str]] = []
    global_frame_cursor = 0

    try:
        for label, npz_path, keras_path in segments:
            print(f"  · {label}")
            if keras_path is not None:
                import keras
                model = keras.models.load_model(str(keras_path))
            else:
                model = build_model()
                _load_weights_into(model, npz_path)

            for frame in _render_title_card(
                width, height,
                [label, f"seed={seed}"],
                title_hold,
            ):
                writer.append_data(frame)
            # Title cards are silent — advance cursor without recording events.
            global_frame_cursor += title_hold

            env = NeonHighwayEnv(seed=seed, max_frames=max_frames)
            gen_num_extracted: Optional[int] = None
            if npz_path is not None:
                m = re.search(r"gen(\d+)", npz_path.name)
                if m:
                    gen_num_extracted = int(m.group(1))

            segment_start = global_frame_cursor
            while not env.done:
                obs = observe(env)
                action = predict_action(model, obs)
                env.step(action)
                hud = {
                    "generation": gen_num_extracted if gen_num_extracted is not None else "final",
                    "fitness": env.fitness(),
                    "title": label,
                }
                renderer.draw(env, hud=hud)
                writer.append_data(renderer.frame_array())

            # Translate this segment's events into global timeline.
            for frame_idx, ev_type in env.events:
                all_events.append((segment_start + frame_idx, ev_type))
            global_frame_cursor += env._frames_alive

            print(f"    score={env.score} fitness={env.fitness():.0f} "
                  f"songs={env.songs_completed} frames={env._frames_alive} "
                  f"events={len(env.events)}")
    finally:
        writer.close()
        renderer.close()

    if with_audio:
        print(f"Synthesising audio track ({len(all_events)} events)…")
        _build_audio_track(
            events=all_events,
            total_frames=global_frame_cursor,
            fps=C.FPS,
            seed=seed,
            out_wav=wav_path,
        )
        print(f"Muxing audio + video → {record_path}")
        _mux_audio_video(video_path, wav_path, record_path)
        # Clean up temp files
        try:
            video_path.unlink()
            wav_path.unlink()
            tmp_dir.rmdir()
        except OSError:
            pass

    print(f"Wrote {record_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default="evolution.mp4")
    ap.add_argument("--checkpoints", default="checkpoints")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-frames", type=int, default=60 * 30,
                    help="Per-segment frame cap (default 30 s).")
    ap.add_argument("--include-final", action="store_true",
                    help="Append best.keras as the final segment.")
    ap.add_argument("--title-card-seconds", type=float, default=1.2)
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--no-audio", action="store_true",
                    help="Skip procedural audio (faster, silent output).")
    args = ap.parse_args()

    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"

    make_video(
        record_path=Path(args.record),
        ckpt_dir=Path(args.checkpoints),
        seed=args.seed,
        max_frames=args.max_frames,
        include_final=args.include_final,
        title_card_seconds=args.title_card_seconds,
        with_audio=not args.no_audio,
    )


if __name__ == "__main__":
    main()
