"""
Run the best evolved genome in the pygame renderer and write an MP4.

Usage:
  python main.py replay --genome checkpoints/best.keras --seed 42
  python main.py replay --genome checkpoints/best.keras --record out.mp4

The recorder uses imageio's ffmpeg pipe — much friendlier than calling
cv2.VideoWriter, and the dependency comes via imageio-ffmpeg which
ships its own static binary, so no system ffmpeg required.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import keras
import numpy as np

from game import config as C
from game.engine import NeonHighwayEnv
from game.renderer import Renderer
from nn.model import predict_action
from nn.observe import observe


def load_genome(path: str) -> keras.Model:
    return keras.models.load_model(path)


def replay(
    genome_path: str,
    seed: int = 42,
    record_path: Optional[str] = None,
    generation: Optional[int] = None,
    title: Optional[str] = None,
    headless: bool = False,
) -> None:
    """
    Run the saved model in the game and (optionally) record an MP4.

    `headless=True` skips pygame.display.set_mode (useful on CI / Linux
    servers without an X session). The renderer still draws to an
    off-screen surface so we can capture frames.
    """
    if headless:
        import os
        os.environ["SDL_VIDEODRIVER"] = "dummy"

    model = load_genome(genome_path)
    env = NeonHighwayEnv(seed=seed, max_frames=60 * 600)  # generous cap for replay
    renderer = Renderer(title=title or "Neon Highway · Best Agent")

    writer = None
    if record_path is not None:
        import imageio.v2 as imageio  # type: ignore
        writer = imageio.get_writer(
            record_path, fps=C.FPS, codec="libx264", quality=8,
            macro_block_size=1,
        )

    try:
        while not env.done:
            # Drain pygame events so the window stays responsive
            import pygame
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    env.phase = "gameover"
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    env.phase = "gameover"

            obs = observe(env)
            action = predict_action(model, obs)
            env.step(action)

            hud = {
                "generation": generation if generation is not None else "best",
                "fitness": env.fitness(),
            }
            if title:
                hud["title"] = title

            renderer.draw(env, hud=hud)
            if writer is not None:
                writer.append_data(renderer.frame_array())
            renderer.flip()
    finally:
        if writer is not None:
            writer.close()
        renderer.close()

    print(f"Replay done · score={env.score} fitness={env.fitness():.0f} "
          f"frames={env._frames_alive} level={env._level_reached}")
