"""
Game constants ported verbatim from the original Neon Highway game
(HW1/assignment1-exercise4/js/cfg.js). Do not edit values here without
also bumping the version note below — the GA training relies on these
matching the live web game so behavior transfers.

Source line references are kept in comments so future-me (or a TA)
can verify the port against the original JS.
"""

# Lane X positions — cfg.js:319
LANES = (-4.2, 0.0, 4.2)
NUM_LANES = 3

# Z-axis layout — cfg.js:320-322
PLAYER_Z = 5.0
SPAWN_Z = -90.0
DESPAWN_Z = 13.0

# Hit detection — cfg.js:345
HIT_WINDOW = 1.6  # z-units from player center

# Lives — cfg.js:344
STARTING_LIVES = 3

# Scoring — cfg.js:347-348
POINTS_BASE = 150
COMBO_MULTS = (1, 2, 4, 8, 16, 32)

# Level progression — cfg.js:323-333
LEVEL_DURATION = 30.0  # seconds before level-up
LEVELS = (
    # (speed [u/s], beat interval [ms])
    (35, 480),
    (44, 440),
    (53, 395),
    (62, 350),
    (72, 310),
    (80, 275),
)

# Player physics — cfg.js:353-355, player.js:41-66
JUMP_FORCE = 12.0
GRAVITY = 28.0
GROUND_Y = 0.5
LATERAL_LERP_K = 13.0  # car.x += (target - x) * min(dt * k, 1)

# Spawn intervals (ms) — cfg.js:357-366
BOLT_INTERVAL_MS = 8000
HEART_INTERVAL_MS = 15000
BIRD_INTERVAL_MS = 12000
COIN_INTERVAL_MS = 3000

# Drone spawn intervals per level — main.js:59
# index = level-1; None means no drones at that level
DRONE_INTERVALS_MS = (None, None, 20000, 14000, 10000, 7000)

# Bird/drone airborne hit zone — cfg.js:362-365
BIRD_Y = 3.0
BIRD_HIT_MIN_Y = 2.0
BIRD_HIT_MAX_Y = 4.1

# Coin float height — cfg.js:370
COIN_Y = 1.2

# Power-up effects — cfg.js:358-359
BOOST_DURATION = 3.0
BOOST_SPEED_MULT = 1.5

# Drone laser — blocks.js:175-176
LASER_SPEED = 55.0
LASER_COOLDOWN = 0.6
LASER_HIT_RADIUS_SQ = 2.25  # 1.5 unit radius

# Sim cadence — fixed step for GA determinism (chose 60 FPS like browser)
FPS = 60
DT = 1.0 / FPS
