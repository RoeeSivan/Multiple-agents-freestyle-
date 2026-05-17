"""
Headless port of Neon Highway's gameplay loop.

This is a faithful re-implementation of the original Three.js game's logic
(see HW1/assignment1-exercise4/js/{main,blocks,player,state}.js), with all
visual / audio / cosmetic code stripped out. We keep only what affects
score, lives, or movement — i.e. what a neural network needs to react to.

Key differences vs. browser game:
  * Fixed timestep (1/60 s) instead of clamped delta-time — required for
    deterministic GA fitness.
  * `numpy.random.Generator` for everything stochastic — seedable, so two
    genomes in the same generation see the same obstacle stream.
  * Real-time `setInterval` spawn timers are replaced with elapsed-time
    accumulators that fire at the same effective ms intervals.
  * Power-ups, lives, scoring all match original numerical values exactly.

The engine is *pure logic*. A separate renderer module (game/renderer.py)
visualises the same state for replay videos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from . import config as C
from .patterns import PATTERNS


# Discrete action space — what the NN outputs (argmax of 4 logits)
ACTION_NOOP = 0
ACTION_LEFT = 1
ACTION_RIGHT = 2
ACTION_JUMP = 3

# A small debounce so the NN can't oscillate lanes every frame. The original
# game's lateral lerp constant (k=13) lets the car visually catch up in ~150ms;
# we mirror that by ignoring lane-change inputs for a few frames after a swap.
LANE_CHANGE_COOLDOWN_FRAMES = 6


@dataclass
class Block:
    """A spawned obstacle / pickup. Mirrors `state.blocks[*]` in state.js."""
    lane: int
    type: str  # 'red' | 'green' | 'bolt' | 'heart' | 'bird' | 'drone' | 'coin'
    z: float
    processed: bool = False
    last_shot: float = 0.0  # only meaningful for drones


@dataclass
class Laser:
    """A drone projectile. Mirrors `state.lasers[*]`."""
    x: float
    y: float
    z: float
    dx: float
    dy: float
    dz: float


class NeonHighwayEnv:
    """
    Single-instance headless game environment.

    Usage:
        env = NeonHighwayEnv(seed=42)
        env.reset()
        while not env.done:
            obs = env.observe()  # 16-dim feature vector for the NN
            action = nn.predict(obs)
            env.step(action)
        score = env.score
        fitness = env.fitness()
    """

    def __init__(self, seed: int = 0, max_frames: int = 60 * 180):
        # Seed: each genome in one generation gets the same seed so fitness
        # comparisons are fair. The trainer bumps the seed per generation.
        self.rng = np.random.default_rng(seed)
        self.max_frames = max_frames
        self._frame = 0
        self.reset()

    # ------------------------------------------------------------------ reset
    def reset(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.rng = np.random.default_rng(seed)

        # Player state — mirrors state.js fields
        self.phase = "playing"
        self.lane = 1
        self.target_x = C.LANES[1]
        self.player_x = C.LANES[1]
        self.player_y = C.GROUND_Y
        self.player_z = C.PLAYER_Z
        self.jump_velocity = 0.0
        self.jumps_used = 0
        self.lives = C.STARTING_LIVES
        self.shielded = False
        self.boost_until = 0.0

        # Progression
        self.score = 0
        self.combo = 0
        self.greens_collected = 0
        self.elapsed = 0.0
        self.level = 1
        self.speed = C.LEVELS[0][0]
        self.last_level_up = 0.0
        self.pattern_idx = 0

        # Spawn tickers (ms-based to match original setInterval cadence)
        self._beat_acc_ms = 0.0
        self._bolt_acc_ms = 0.0
        self._heart_acc_ms = 0.0
        self._bird_acc_ms = 0.0
        self._coin_acc_ms = 0.0
        self._drone_acc_ms = 0.0

        # Active world entities
        self.blocks: List[Block] = []
        self.lasers: List[Laser] = []

        # Bookkeeping
        self._frame = 0
        self._lane_cooldown = 0
        self._frames_alive = 0
        self._died_out_of_bounds = False
        self._level_reached = 1

        # Audio event log — (frame_idx, event_type). Consumed offline by
        # scripts/make_evolution_video.py to synth original game sounds.
        # Cosmetic only; fitness untouched.
        self.events: List[Tuple[int, str]] = []

    # ----------------------------------------------------------------- public
    @property
    def done(self) -> bool:
        return self.phase != "playing" or self._frame >= self.max_frames

    def step(self, action: int) -> None:
        """Advance one fixed-dt frame after applying `action`."""
        if self.done:
            return

        self._apply_action(action)
        dt = C.DT
        self.elapsed += dt
        self._frame += 1
        self._frames_alive += 1
        if self._lane_cooldown > 0:
            self._lane_cooldown -= 1

        self._check_level_up()
        self._expire_boost()
        self._tick_player(dt)
        self._tick_spawns(dt)
        self._tick_blocks(dt)
        self._tick_lasers(dt)
        self._process_collisions()
        self._process_laser_collisions()

    # ----------------------------------------------------------------- action
    def _apply_action(self, action: int) -> None:
        if action == ACTION_LEFT or action == ACTION_RIGHT:
            if self._lane_cooldown > 0:
                return
            direction = -1 if action == ACTION_LEFT else 1
            self._handle_lane_change(direction)
            self._lane_cooldown = LANE_CHANGE_COOLDOWN_FRAMES
        elif action == ACTION_JUMP:
            self._handle_jump()
        # ACTION_NOOP — do nothing

    def _handle_lane_change(self, direction: int) -> None:
        # Mirrors main.js:18-40 — stepping off the road costs a life
        # unless shielded.
        nxt = self.lane + direction
        if nxt < 0 or nxt > 2:
            if self.shielded:
                self.shielded = False
                return
            self.lives -= 1
            self.combo = 0
            self._died_out_of_bounds = True
            self.events.append((self._frame, "collision"))
            if self.lives <= 0:
                self._trigger_game_over()
            return
        self.lane = nxt
        self.target_x = C.LANES[nxt]
        self._died_out_of_bounds = False  # only flag if death actually OOB

    def _handle_jump(self) -> None:
        # main.js:42-48 — up to two air actions (initial + 1 double-jump).
        if self.jumps_used < 2:
            self.jump_velocity = C.JUMP_FORCE
            self.jumps_used += 1

    # ------------------------------------------------------------ per-frame
    def _tick_player(self, dt: float) -> None:
        # Lateral smoothing — player.js:41-66
        lerp = min(dt * C.LATERAL_LERP_K, 1.0)
        self.player_x += (self.target_x - self.player_x) * lerp

        # Vertical motion — gravity + landing
        self.jump_velocity -= C.GRAVITY * dt
        self.player_y += self.jump_velocity * dt
        if self.player_y <= C.GROUND_Y:
            self.player_y = C.GROUND_Y
            self.jump_velocity = 0.0
            self.jumps_used = 0

    def _check_level_up(self) -> None:
        # main.js:216-229
        if self.elapsed - self.last_level_up < C.LEVEL_DURATION:
            return
        self.last_level_up = self.elapsed
        self.level += 1
        idx = min(self.level - 1, len(C.LEVELS) - 1)
        speed, _ = C.LEVELS[idx]
        # Don't override active speed boost
        if self.boost_until <= self.elapsed:
            self.speed = speed
        self._level_reached = max(self._level_reached, self.level)

    def _expire_boost(self) -> None:
        if self.boost_until > 0 and self.elapsed >= self.boost_until:
            self.boost_until = 0.0
            idx = min(self.level - 1, len(C.LEVELS) - 1)
            self.speed = C.LEVELS[idx][0]

    # ------------------------------------------------------------- spawning
    def _current_beat_ms(self) -> int:
        idx = min(self.level - 1, len(C.LEVELS) - 1)
        return C.LEVELS[idx][1]

    def _tick_spawns(self, dt: float) -> None:
        """Convert ms-based setInterval timers into accumulator-driven spawns."""
        dt_ms = dt * 1000.0

        # Pattern beat — main.js:197-203
        self._beat_acc_ms += dt_ms
        beat_ms = self._current_beat_ms()
        while self._beat_acc_ms >= beat_ms:
            self._beat_acc_ms -= beat_ms
            self._spawn_pattern_beat()

        # Bolt — blocks.js:223-231
        self._bolt_acc_ms += dt_ms
        while self._bolt_acc_ms >= C.BOLT_INTERVAL_MS:
            self._bolt_acc_ms -= C.BOLT_INTERVAL_MS
            self._spawn_random("bolt")

        # Heart — blocks.js:124-132
        self._heart_acc_ms += dt_ms
        while self._heart_acc_ms >= C.HEART_INTERVAL_MS:
            self._heart_acc_ms -= C.HEART_INTERVAL_MS
            self._spawn_random("heart")

        # Bird — blocks.js:156-162
        self._bird_acc_ms += dt_ms
        while self._bird_acc_ms >= C.BIRD_INTERVAL_MS:
            self._bird_acc_ms -= C.BIRD_INTERVAL_MS
            self._spawn_random("bird")

        # Coin — blocks.js:234-245
        self._coin_acc_ms += dt_ms
        while self._coin_acc_ms >= C.COIN_INTERVAL_MS:
            self._coin_acc_ms -= C.COIN_INTERVAL_MS
            self._spawn_random("coin")

        # Drone — main.js:205-214 (level-gated)
        idx = min(self.level - 1, len(C.DRONE_INTERVALS_MS) - 1)
        drone_ms = C.DRONE_INTERVALS_MS[idx]
        if drone_ms is not None:
            self._drone_acc_ms += dt_ms
            while self._drone_acc_ms >= drone_ms:
                self._drone_acc_ms -= drone_ms
                self._spawn_random("drone")

    def _spawn_pattern_beat(self) -> None:
        pat = PATTERNS[self.pattern_idx % len(PATTERNS)]
        for lane, type_ in pat:
            self.blocks.append(Block(lane=lane, type=type_, z=C.SPAWN_Z))
        self.pattern_idx += 1

    def _spawn_random(self, type_: str) -> None:
        lane = int(self.rng.integers(0, 3))
        self.blocks.append(Block(lane=lane, type=type_, z=C.SPAWN_Z))

    # ---------------------------------------------------------- block ticks
    def _tick_blocks(self, dt: float) -> None:
        # blocks.js:257-300
        survivors: List[Block] = []
        for b in self.blocks:
            b.z += self.speed * dt

            # Drone shooting — blocks.js:274-281
            if (
                b.type == "drone"
                and -30.0 < b.z < C.PLAYER_Z
                and self.elapsed - b.last_shot >= C.LASER_COOLDOWN
            ):
                b.last_shot = self.elapsed
                self._spawn_laser_at(b)

            if b.z <= C.DESPAWN_Z:
                survivors.append(b)
        self.blocks = survivors

    def _spawn_laser_at(self, drone: Block) -> None:
        # blocks.js:185-201 — laser aims at car's current position.
        src_x = C.LANES[drone.lane]
        src_y = C.BIRD_Y
        src_z = drone.z
        dx = self.player_x - src_x
        dy = self.player_y - src_y
        dz = self.player_z - src_z
        length = max((dx * dx + dy * dy + dz * dz) ** 0.5, 1e-6)
        self.lasers.append(
            Laser(
                x=src_x, y=src_y, z=src_z,
                dx=dx / length, dy=dy / length, dz=dz / length,
            )
        )

    def _tick_lasers(self, dt: float) -> None:
        # blocks.js:203-216
        survivors: List[Laser] = []
        for l in self.lasers:
            l.x += l.dx * C.LASER_SPEED * dt
            l.y += l.dy * C.LASER_SPEED * dt
            l.z += l.dz * C.LASER_SPEED * dt
            if l.z <= C.DESPAWN_Z and l.y >= -5.0:
                survivors.append(l)
        self.lasers = survivors

    # -------------------------------------------------------- collision
    def _process_collisions(self) -> None:
        # main.js:278-387
        for b in self.blocks:
            if b.processed:
                continue
            if abs(b.z - C.PLAYER_Z) > C.HIT_WINDOW:
                continue
            b.processed = True
            in_lane = b.lane == self.lane

            if b.type == "heart":
                if in_lane and not self.shielded:
                    self.shielded = True
            elif b.type == "bolt":
                if in_lane:
                    self.boost_until = self.elapsed + C.BOOST_DURATION
                    idx = min(self.level - 1, len(C.LEVELS) - 1)
                    self.speed = C.LEVELS[idx][0] * C.BOOST_SPEED_MULT
            elif b.type == "coin":
                airborne = self.player_y > C.COIN_Y + 1.0
                if in_lane and not airborne:
                    self.events.append((self._frame, "coin"))
            elif b.type in ("bird", "drone"):
                in_flight = (
                    in_lane
                    and C.BIRD_HIT_MIN_Y <= self.player_y <= C.BIRD_HIT_MAX_Y
                )
                if in_flight:
                    self.events.append((self._frame, "collision"))
                    self._take_hit()
                    if self.lives <= 0:
                        return
            elif b.type == "green":
                if in_lane:
                    self.combo += 1
                    mult_idx = min(self.combo - 1, len(C.COMBO_MULTS) - 1)
                    self.score += C.POINTS_BASE * C.COMBO_MULTS[mult_idx]
                    self.greens_collected += 1
                    self.events.append((self._frame, "green"))
                else:
                    self.combo = 0
            else:  # 'red' obstacle
                airborne = self.player_y > C.GROUND_Y + 0.3
                if in_lane and not airborne:
                    self.events.append((self._frame, "collision"))
                    self._take_hit()
                    if self.lives <= 0:
                        return

    def _process_laser_collisions(self) -> None:
        # main.js:390-419
        survivors: List[Laser] = []
        for l in self.lasers:
            dx = l.x - self.player_x
            dy = l.y - self.player_y
            dz = l.z - self.player_z
            if dx * dx + dy * dy + dz * dz <= C.LASER_HIT_RADIUS_SQ:
                if self.shielded:
                    self.shielded = False
                    continue
                self.events.append((self._frame, "laser_hit"))
                self._take_hit()
                if self.lives <= 0:
                    return
                continue
            survivors.append(l)
        self.lasers = survivors

    def _take_hit(self) -> None:
        if self.shielded:
            self.shielded = False
            return
        self.lives -= 1
        self.combo = 0
        if self.lives <= 0:
            self._trigger_game_over()

    def _trigger_game_over(self) -> None:
        self.phase = "gameover"

    # --------------------------------------------------------------- fitness
    @property
    def songs_completed(self) -> int:
        return self.greens_collected // C.NOTES_PER_SONG

    def fitness(self) -> float:
        """
        Composite fitness function — see plan doc for rationale.

        * score is the dominant signal (green collection × combo).
        * frames_alive is a small survival bonus (so an agent that survives
          longer but happens to miss greens still beats one that crashes
          instantly).
        * level bonus rewards progression past the easy first 30 s.
        * song bonus rewards finishing whole melodies (raw greens / NOTES_PER_SONG),
          so replay videos sound musical instead of chaotic.
        * OOB penalty discourages the trivial "walk off the road" strategy.
        """
        oob_penalty = 200.0 if self._died_out_of_bounds and self.lives <= 0 else 0.0
        return (
            float(self.score)
            + 0.1 * self._frames_alive
            + 50.0 * (self._level_reached - 1)
            + C.SONG_BONUS * self.songs_completed
            - oob_penalty
        )

    # ---------------------------------------------------- observation helper
    def nearest_per_lane(self) -> List[Tuple[float, str]]:
        """
        For each of the 3 lanes, return the nearest *ahead* block as a
        (delta_z, type) tuple. delta_z is positive when the block is in
        front of the player; we cap to SPAWN_Z if no block exists.
        """
        nearest = [(C.PLAYER_Z - C.SPAWN_Z, "none")] * 3
        for b in self.blocks:
            if b.processed:
                continue
            dz = C.PLAYER_Z - b.z  # >0 = ahead
            if dz <= 0:  # already passed
                continue
            if dz < nearest[b.lane][0]:
                nearest[b.lane] = (dz, b.type)
        return nearest
