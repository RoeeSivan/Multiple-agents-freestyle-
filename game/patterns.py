"""
Spawn patterns ported from blocks.js:76-89.

Each pattern is a list of (lane, type) pairs spawned together on one beat.
The original cycles through this 12-pattern array with state.patternIdx.
"""

PATTERNS = (
    ((1, "green"),),
    ((0, "green"), (2, "red")),
    ((2, "green"),),
    ((1, "red"), (0, "green")),
    ((0, "green"), (1, "green")),
    ((2, "red"), (1, "green")),
    ((1, "green"), (0, "red")),
    ((0, "green"),),
    ((2, "green"), (1, "red")),
    ((1, "green"), (2, "green")),
    ((0, "red"), (2, "green")),
    ((1, "red"),),
)
