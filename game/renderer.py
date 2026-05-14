"""
Top-down pygame renderer for Neon Highway.

NOT used during GA training (training is headless for speed). This module
exists only to:

  1. Let a human play the Python clone with the keyboard, to manually
     compare feel against the live web game.
  2. Replay the best evolved genome and capture a video for the
     submission.

The visual style is deliberately schematic (neon shapes on black) — the
goal is "looks like the same game" not "pixel-perfect" — because anything
prettier is wasted effort for the assignment.
"""
from __future__ import annotations

from typing import Optional

import pygame

from . import config as C
from .engine import (
    ACTION_JUMP,
    ACTION_LEFT,
    ACTION_NOOP,
    ACTION_RIGHT,
    NeonHighwayEnv,
)


# Window / world mapping
SCREEN_W = 540
SCREEN_H = 720
LANE_PIXEL_W = 120
ROAD_LEFT = (SCREEN_W - 3 * LANE_PIXEL_W) // 2
PLAYER_SCREEN_Y = 580  # near bottom of screen
# z (world) → y (screen): SPAWN_Z (-90) maps to top, PLAYER_Z (5) maps to PLAYER_SCREEN_Y
Z_RANGE = C.PLAYER_Z - C.SPAWN_Z  # 95.0
TOP_MARGIN = 80


# Neon palette
COLOR_BG = (8, 0, 20)
COLOR_ROAD = (18, 4, 38)
COLOR_LANE_LINE = (90, 50, 140)
COLOR_PLAYER = (0, 255, 200)
COLOR_PLAYER_SHIELD = (0, 255, 255)
COLOR_GREEN = (0, 255, 90)
COLOR_RED = (255, 60, 60)
COLOR_BOLT = (255, 215, 0)
COLOR_HEART = (255, 80, 200)
COLOR_BIRD = (255, 140, 0)
COLOR_DRONE = (220, 100, 255)
COLOR_COIN = (255, 200, 60)
COLOR_LASER = (255, 0, 0)
COLOR_HUD = (220, 220, 240)
COLOR_HUD_DIM = (140, 140, 160)


BLOCK_COLORS = {
    "green": COLOR_GREEN,
    "red": COLOR_RED,
    "bolt": COLOR_BOLT,
    "heart": COLOR_HEART,
    "bird": COLOR_BIRD,
    "drone": COLOR_DRONE,
    "coin": COLOR_COIN,
}


def lane_to_screen_x(lane: int) -> int:
    return ROAD_LEFT + LANE_PIXEL_W * lane + LANE_PIXEL_W // 2


def world_x_to_screen(world_x: float) -> int:
    # Map continuous x in [-4.2, 4.2] (the LANES range) to the road area
    # so the lateral lerp animation actually shows.
    normalised = (world_x - C.LANES[0]) / (C.LANES[2] - C.LANES[0])  # 0..1
    return int(ROAD_LEFT + normalised * 3 * LANE_PIXEL_W)


def world_z_to_screen_y(world_z: float) -> int:
    # SPAWN_Z (-90) → TOP_MARGIN, PLAYER_Z (5) → PLAYER_SCREEN_Y
    t = (world_z - C.SPAWN_Z) / Z_RANGE
    return int(TOP_MARGIN + t * (PLAYER_SCREEN_Y - TOP_MARGIN))


class Renderer:
    """Wraps a pygame window. Stateless w.r.t. the environment."""

    def __init__(self, title: str = "Neon Highway · GA Replay"):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("Consolas,Menlo,monospace", 18, bold=True)
        self.font_big = pygame.font.SysFont("Consolas,Menlo,monospace", 28, bold=True)
        self.font_small = pygame.font.SysFont("Consolas,Menlo,monospace", 14)

    def draw(self, env: NeonHighwayEnv, hud: Optional[dict] = None) -> None:
        self.screen.fill(COLOR_BG)
        self._draw_road()
        self._draw_blocks(env)
        self._draw_lasers(env)
        self._draw_player(env)
        self._draw_hud(env, hud or {})

    def flip(self, fps: int = C.FPS) -> None:
        pygame.display.flip()
        self.clock.tick(fps)

    def frame_array(self):
        """RGB ndarray of the current frame — for video capture."""
        return pygame.surfarray.array3d(self.screen).swapaxes(0, 1)

    def close(self) -> None:
        pygame.quit()

    # --------------------------------------------------------------- private
    def _draw_road(self) -> None:
        road_rect = pygame.Rect(
            ROAD_LEFT, TOP_MARGIN, 3 * LANE_PIXEL_W, PLAYER_SCREEN_Y - TOP_MARGIN + 80
        )
        pygame.draw.rect(self.screen, COLOR_ROAD, road_rect)
        # Lane dividers
        for i in range(1, 3):
            x = ROAD_LEFT + i * LANE_PIXEL_W
            for y in range(TOP_MARGIN, PLAYER_SCREEN_Y + 80, 24):
                pygame.draw.line(
                    self.screen, COLOR_LANE_LINE, (x, y), (x, y + 12), 2
                )

    def _draw_blocks(self, env: NeonHighwayEnv) -> None:
        for b in env.blocks:
            color = BLOCK_COLORS.get(b.type, (200, 200, 200))
            x = lane_to_screen_x(b.lane)
            y = world_z_to_screen_y(b.z)
            if not (TOP_MARGIN - 30 <= y <= SCREEN_H):
                continue
            # Perspective shrink: blocks ahead drawn smaller
            t = (b.z - C.SPAWN_Z) / Z_RANGE
            size = int(20 + 50 * max(t, 0))
            rect = pygame.Rect(x - size // 2, y - size // 2, size, size)
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            pygame.draw.rect(self.screen, (255, 255, 255), rect, 1, border_radius=4)

    def _draw_lasers(self, env: NeonHighwayEnv) -> None:
        for l in env.lasers:
            t = (l.z - C.SPAWN_Z) / Z_RANGE
            size = int(4 + 8 * max(t, 0))
            sx = world_x_to_screen(l.x)
            sy = world_z_to_screen_y(l.z)
            pygame.draw.circle(self.screen, COLOR_LASER, (sx, sy), size)

    def _draw_player(self, env: NeonHighwayEnv) -> None:
        sx = world_x_to_screen(env.player_x)
        # Player Y rendered as a small upward offset proportional to jump height
        air_offset = int(env.player_y * 10)
        sy = PLAYER_SCREEN_Y - air_offset
        color = COLOR_PLAYER_SHIELD if env.shielded else COLOR_PLAYER
        rect = pygame.Rect(sx - 30, sy - 22, 60, 44)
        pygame.draw.rect(self.screen, color, rect, border_radius=8)
        pygame.draw.rect(self.screen, (255, 255, 255), rect, 2, border_radius=8)
        # shadow under player (gives jump feedback)
        shadow_rect = pygame.Rect(sx - 24, PLAYER_SCREEN_Y + 22, 48, 6)
        pygame.draw.ellipse(self.screen, (0, 0, 0, 80), shadow_rect)

    def _draw_hud(self, env: NeonHighwayEnv, extras: dict) -> None:
        lines = [
            ("Gen",   str(extras.get("generation", "—"))),
            ("Fitness", f"{extras.get('fitness', env.fitness()):.0f}"),
            ("Score", str(env.score)),
            ("Lives", str(env.lives)),
            ("Level", str(env.level)),
            ("Speed", f"{env.speed:.0f}"),
            ("Combo", str(env.combo)),
        ]
        y = 8
        for label, value in lines:
            label_surf = self.font_small.render(label, True, COLOR_HUD_DIM)
            value_surf = self.font.render(value, True, COLOR_HUD)
            self.screen.blit(label_surf, (12, y))
            self.screen.blit(value_surf, (70, y - 3))
            y += 22

        # Center title — useful in the recording
        title = extras.get("title")
        if title:
            t_surf = self.font_big.render(title, True, COLOR_HUD)
            self.screen.blit(t_surf, (SCREEN_W // 2 - t_surf.get_width() // 2, 10))

        if env.shielded:
            s = self.font_small.render("SHIELD", True, COLOR_PLAYER_SHIELD)
            self.screen.blit(s, (SCREEN_W - 80, 12))
        if env.boost_until > env.elapsed:
            s = self.font_small.render("BOOST", True, COLOR_BOLT)
            self.screen.blit(s, (SCREEN_W - 80, 30))


# ---------------------------------------------------------------- human play
KEY_TO_ACTION = {
    pygame.K_LEFT: ACTION_LEFT,
    pygame.K_a: ACTION_LEFT,
    pygame.K_RIGHT: ACTION_RIGHT,
    pygame.K_d: ACTION_RIGHT,
    pygame.K_SPACE: ACTION_JUMP,
}


def play_human(seed: int = 0) -> None:
    """Run the Python clone with keyboard input — sanity check vs. the web game."""
    env = NeonHighwayEnv(seed=seed, max_frames=60 * 600)
    renderer = Renderer(title="Neon Highway · Human")
    running = True
    while running and not env.done:
        action = ACTION_NOOP
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in KEY_TO_ACTION:
                    action = KEY_TO_ACTION[event.key]
        env.step(action)
        renderer.draw(env, hud={"title": "HUMAN"})
        renderer.flip()
    renderer.close()
    print(f"Game over · score={env.score} fitness={env.fitness():.0f}")
