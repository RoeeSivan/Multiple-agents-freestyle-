"""
Keras model factory + weight ops for the GA.

We use the Keras NumPy backend (set via env var KERAS_BACKEND=numpy in
main.py before any Keras import). For genetic algorithms over fixed-
topology MLPs the NumPy backend wins on every axis: no GPU init lag,
no graph compilation, no autograd overhead, identical numerics. The TF
backend would only matter if we did backprop, which we don't.

Inspired by github.com/dk8827/flappy_nn — same backend choice, same
"GA mutates set_weights() directly" pattern.
"""
from __future__ import annotations

import math
from typing import List, Sequence

import numpy as np
import keras
from keras import layers


# --------------------------------------------------------- Architecture
# Inputs (16) — see nn/observe.py for the exact feature layout.
INPUT_DIM = 16

# Hidden layers — small on purpose. GA on big nets is wasteful: each
# weight is independent, so doubling the param count quadruples the
# search space.
HIDDEN = (24, 16)

# Outputs (4): noop, left, right, jump (argmax)
OUTPUT_DIM = 4


def build_model() -> keras.Model:
    """Fresh model with default (untrained) weights."""
    model = keras.Sequential(
        [
            layers.Input(shape=(INPUT_DIM,)),
            layers.Dense(HIDDEN[0], activation="tanh"),
            layers.Dense(HIDDEN[1], activation="tanh"),
            layers.Dense(OUTPUT_DIM, activation="linear"),
        ]
    )
    # Force a forward pass to materialise weight tensors under numpy backend
    model(np.zeros((1, INPUT_DIM), dtype=np.float32), training=False)
    return model


def randomize_model(model: keras.Model, rng: np.random.Generator) -> None:
    """
    Replace weights with N(0, σ) where σ is layer-scaled. Same scaling
    rule as flappy_nn — empirically works well as a GA starting point
    because outputs stay in a reasonable range and tanh doesn't saturate.
    """
    new_weights = []
    for w in model.get_weights():
        scale = 1.0 / max(1.0, math.sqrt(w.size))
        new_weights.append(
            rng.normal(0.0, scale * 2.2, size=w.shape).astype(np.float32)
        )
    model.set_weights(new_weights)


def predict_action(model: keras.Model, obs: np.ndarray) -> int:
    """Run one inference and return argmax action."""
    obs_batched = obs.astype(np.float32, copy=False)[None, :]
    logits = model(obs_batched, training=False)
    # In numpy backend `model(...)` returns a numpy array already.
    return int(np.argmax(np.asarray(logits)[0]))


# --------------------------------------------------------- GA weight ops
def clone_weights(model: keras.Model) -> List[np.ndarray]:
    """Deep-copy of `get_weights()` so subsequent mutations don't alias."""
    return [w.copy() for w in model.get_weights()]


def set_weights_into(model: keras.Model, weights: Sequence[np.ndarray]) -> None:
    model.set_weights([w.copy() for w in weights])


def uniform_crossover(
    parent_a: Sequence[np.ndarray],
    parent_b: Sequence[np.ndarray],
    rng: np.random.Generator,
) -> List[np.ndarray]:
    """Per-scalar 50/50 mask between parents. Cheap and effective."""
    child = []
    for wa, wb in zip(parent_a, parent_b):
        mask = rng.random(size=wa.shape) < 0.5
        child.append(np.where(mask, wa, wb).astype(np.float32))
    return child


def gaussian_mutate(
    weights: Sequence[np.ndarray],
    rate: float,
    sigma: float,
    rng: np.random.Generator,
) -> List[np.ndarray]:
    """
    With probability `rate` per scalar, add N(0, sigma). Sigma is annealed
    by the trainer over generations so early gens explore, late gens
    fine-tune.
    """
    out = []
    for w in weights:
        noise = rng.normal(0.0, sigma, size=w.shape).astype(np.float32)
        mask = rng.random(size=w.shape) < rate
        out.append(np.where(mask, w + noise, w))
    return out
