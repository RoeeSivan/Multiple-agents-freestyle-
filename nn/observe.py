"""
Feature extractor — turn an env state into a 16-d vector for the NN.

Design notes:
  * Everything is normalised to roughly [-1, 1] so tanh layers stay
    responsive (saturating tanh kills GA gradient signal — yes, even
    without backprop, because mutations to saturated weights have no
    behavioral effect).
  * Per-lane nearest-hazard encoding is the heart of the observation:
    the network needs to know "what's coming, in which lane, how
    soon, friend or foe".
  * Types collapse to a single scalar in [-1, 1]: red < bird/drone < none
    < bolt/heart < green/coin. Lets one neuron decide "approach or
    avoid" instead of needing a one-hot per type.
"""
from __future__ import annotations

import numpy as np

from game import config as C
from game.engine import NeonHighwayEnv


# Map block types → scalar in [-1, 1]
_TYPE_CODE = {
    "red": -1.0,
    "bird": -0.6,
    "drone": -0.6,
    "none": 0.0,
    "bolt": 0.5,
    "heart": 0.7,
    "coin": 0.8,
    "green": 1.0,
}


def observe(env: NeonHighwayEnv) -> np.ndarray:
    """16-dim observation vector — see comments for layout."""
    out = np.zeros(16, dtype=np.float32)

    # [0] continuous player x (lateral lerp in-progress shows here)
    out[0] = env.player_x / 4.2

    # [1] jump height (0 on ground, ~0.8 at jump apex)
    out[1] = env.player_y / 5.0

    # [2..4] one-hot current lane
    out[2 + env.lane] = 1.0

    # [5] jump velocity sign+magnitude (positive = rising)
    out[5] = env.jump_velocity / C.JUMP_FORCE

    # [6] jumps remaining
    out[6] = (2 - env.jumps_used) / 2.0

    # [7] shielded flag
    out[7] = 1.0 if env.shielded else 0.0

    # [8] boost active flag
    out[8] = 1.0 if env.boost_until > env.elapsed else 0.0

    # [9..14] per-lane nearest hazard: (dz_norm, type_code) × 3 lanes
    nearest = env.nearest_per_lane()
    span = C.PLAYER_Z - C.SPAWN_Z  # 95
    for i, (dz, type_) in enumerate(nearest):
        out[9 + i * 2] = max(0.0, min(1.0, dz / span))
        out[10 + i * 2] = _TYPE_CODE.get(type_, 0.0)

    # [15] speed (normalised against final-level speed)
    out[15] = env.speed / 80.0

    return out
