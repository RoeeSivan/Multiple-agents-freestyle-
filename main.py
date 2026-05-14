"""
CLI entry point.

Subcommands:
  train   — run GA training, live chart, save best.keras
  replay  — load best.keras, run game with renderer, optional MP4 recording
  human   — play the Python clone with arrow keys + space (sanity check vs web)
  smoke   — tiny pop/gen config to verify everything wires up end-to-end

Sets KERAS_BACKEND=numpy before importing Keras-touching modules. This
makes Keras skip TensorFlow entirely — fine for tiny MLP inference, and
much faster to launch.
"""
from __future__ import annotations

import argparse
import os
import sys

# Must be set BEFORE any `import keras` anywhere in the project.
os.environ.setdefault("KERAS_BACKEND", "numpy")


def _cmd_train(args: argparse.Namespace) -> None:
    # Deferred imports so KERAS_BACKEND env var takes effect.
    from ga.train import TrainConfig, train
    from viz.live_chart import LiveChart

    cfg = TrainConfig(
        population_size=args.pop,
        generations=args.gens,
        seed=args.seed,
        checkpoint_every=args.checkpoint_every,
        max_frames_per_episode=args.max_frames,
        out_dir=".",
    )
    chart = None if args.no_chart else LiveChart()

    def cb(stats):
        if chart is not None:
            from pathlib import Path
            chart.update(stats, save_path=Path("logs/fitness.png"))

    best = train(cfg, chart_callback=cb)
    print(f"Best ever fitness: {best.fitness:.1f}  (score={best.score}, "
          f"level={best.level}, frames={best.frames})")
    if chart is not None and args.hold:
        chart.hold()


def _cmd_replay(args: argparse.Namespace) -> None:
    from replay.record import replay
    replay(
        genome_path=args.genome,
        seed=args.seed,
        record_path=args.record,
        generation=args.gen,
        title=args.title,
        headless=args.headless,
    )


def _cmd_human(args: argparse.Namespace) -> None:
    from game.renderer import play_human
    play_human(seed=args.seed)


def _cmd_drive_web(args: argparse.Namespace) -> None:
    """Drive the real Three.js game in a headed Chromium via Playwright."""
    from web_driver.drive import drive_web
    drive_web(
        genome_path=args.genome,
        port=args.port,
        record_path=args.record,
        max_duration_s=args.max_duration,
        headless=args.headless,
        web_game_dir=args.web_game_dir,
    )


def _cmd_smoke(args: argparse.Namespace) -> None:
    """Minimal end-to-end check — should finish in < 60 s."""
    from ga.train import TrainConfig, train
    cfg = TrainConfig(
        population_size=8,
        generations=3,
        max_frames_per_episode=300,
        elites=2,
        breeding_pool=4,
        checkpoint_every=99,
    )
    best = train(cfg, chart_callback=None)
    print(f"smoke: best fitness={best.fitness:.1f}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="neon-highway-ga")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_train = sub.add_parser("train", help="run GA training")
    p_train.add_argument("--pop", type=int, default=60)
    p_train.add_argument("--gens", type=int, default=100)
    p_train.add_argument("--seed", type=int, default=1337)
    p_train.add_argument("--checkpoint-every", type=int, default=10)
    p_train.add_argument("--max-frames", type=int, default=60 * 180)
    p_train.add_argument("--no-chart", action="store_true")
    p_train.add_argument("--hold", action="store_true",
                         help="keep the chart window open after training")
    p_train.set_defaults(func=_cmd_train)

    p_replay = sub.add_parser("replay", help="replay a saved genome")
    p_replay.add_argument("--genome", default="checkpoints/best.keras")
    p_replay.add_argument("--seed", type=int, default=42)
    p_replay.add_argument("--record", default=None, help="MP4 output path")
    p_replay.add_argument("--gen", type=int, default=None)
    p_replay.add_argument("--title", default=None)
    p_replay.add_argument("--headless", action="store_true")
    p_replay.set_defaults(func=_cmd_replay)

    p_human = sub.add_parser("human", help="play the Python clone yourself")
    p_human.add_argument("--seed", type=int, default=0)
    p_human.set_defaults(func=_cmd_human)

    p_web = sub.add_parser(
        "drive-web", help="drive the real Three.js game with the trained model"
    )
    p_web.add_argument("--genome", default="checkpoints/best.keras")
    p_web.add_argument("--port", type=int, default=8765)
    p_web.add_argument("--record", default=None, help="output .webm/.mp4 path")
    p_web.add_argument("--max-duration", type=float, default=360.0,
                       help="hard time cap (seconds)")
    p_web.add_argument("--headless", action="store_true")
    p_web.add_argument("--web-game-dir", default="web_game")
    p_web.set_defaults(func=_cmd_drive_web)

    p_smoke = sub.add_parser("smoke", help="tiny GA run for sanity")
    p_smoke.set_defaults(func=_cmd_smoke)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
