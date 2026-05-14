"""
Build a single MP4 showing the agent's evolution across GA generations.

Iterates checkpoints/best_gen*.npz (plus final best.keras) in order. For
each genome: replays one game with a HUD overlay tagging the generation,
and writes the frames into a single shared MP4 writer. Optional title-card
frames separate clips so the viewer sees the gen number for ~1 second
before the gameplay starts.

Usage:
  python scripts/make_evolution_video.py --record evolution.mp4
  python scripts/make_evolution_video.py --record evolution.mp4 --seed 42 \
      --max-frames 1200 --include-final
"""
from __future__ import annotations

import argparse
import os
import re
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


def make_video(
    record_path: Path,
    ckpt_dir: Path,
    seed: int,
    max_frames: int,
    include_final: bool,
    title_card_seconds: float,
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

    writer = imageio.get_writer(
        str(record_path), fps=C.FPS, codec="libx264", quality=8,
        macro_block_size=1,
    )

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

            env = NeonHighwayEnv(seed=seed, max_frames=max_frames)
            gen_num_extracted: Optional[int] = None
            if npz_path is not None:
                m = re.search(r"gen(\d+)", npz_path.name)
                if m:
                    gen_num_extracted = int(m.group(1))

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

            print(f"    score={env.score} fitness={env.fitness():.0f} "
                  f"songs={env.songs_completed} frames={env._frames_alive}")
    finally:
        writer.close()
        renderer.close()

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
    )


if __name__ == "__main__":
    main()
