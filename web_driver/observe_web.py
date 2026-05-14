"""
Build a 16-d observation vector from the JS bridge's `window.gameState()`
return value. Mirrors nn/observe.py exactly so the trained model sees
the same feature layout it learned on.

The original game uses 3 lanes at X = [-4.2, 0, 4.2], spawn Z = -90,
player Z = 5 — identical numerics to game/config.py.
"""
from __future__ import annotations

from typing import Any, Dict

import numpy as np

# Re-use the type encoding from nn/observe.py — single source of truth.
from nn.observe import _TYPE_CODE

# Constants identical to game/config.py (kept local so this module has
# no dependency on the python clone — feature parity matters more than
# DRY here, since the values are nailed down by the original cfg.js).
LANES_X_MAX = 4.2
PLAYER_Z = 5.0
SPAWN_Z = -90.0
SPAN_Z = PLAYER_Z - SPAWN_Z  # 95
LEVEL_TOP_SPEED = 80.0
JUMP_FORCE = 12.0
PLAYER_Y_NORM_MAX = 5.0


def nearest_per_lane_web(blocks):
    """
    Match the env.nearest_per_lane() output but read from the JS
    `blocks` array (each block has lane, type, z fields).
    """
    nearest = [(SPAN_Z, "none"), (SPAN_Z, "none"), (SPAN_Z, "none")]
    for b in blocks:
        if b.get("processed"):
            continue
        dz = PLAYER_Z - float(b["z"])
        if dz <= 0:
            continue
        lane = int(b["lane"])
        if 0 <= lane < 3 and dz < nearest[lane][0]:
            nearest[lane] = (dz, str(b["type"]))
    return nearest


def observe_web(state: Dict[str, Any]) -> np.ndarray:
    """Same 16-d layout as nn/observe.py:observe()."""
    out = np.zeros(16, dtype=np.float32)

    player = state.get("player", {"x": 0, "y": 0, "z": PLAYER_Z})
    lane = int(state.get("lane", 1))

    out[0] = float(player["x"]) / LANES_X_MAX
    out[1] = float(player["y"]) / PLAYER_Y_NORM_MAX
    out[2 + max(0, min(2, lane))] = 1.0
    out[5] = float(state.get("jumpVelocity", 0.0)) / JUMP_FORCE
    out[6] = (2 - int(state.get("jumpsUsed", 0))) / 2.0
    out[7] = 1.0 if state.get("shielded") else 0.0
    out[8] = 1.0 if state.get("boostActive") else 0.0

    nearest = nearest_per_lane_web(state.get("blocks", []))
    for i, (dz, type_) in enumerate(nearest):
        out[9 + i * 2] = max(0.0, min(1.0, dz / SPAN_Z))
        out[10 + i * 2] = _TYPE_CODE.get(type_, 0.0)

    out[15] = float(state.get("speed", 0.0)) / LEVEL_TOP_SPEED
    return out
