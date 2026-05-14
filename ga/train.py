"""
Genetic-algorithm trainer for Neon Highway.

Pipeline per generation:
  1. Evaluate every genome on a single deterministic seed (fair fight).
  2. Rank by fitness.
  3. Keep top-K elites unchanged.
  4. Children = uniform crossover of two parents from the top quartile,
     followed by Gaussian mutation. Sigma + rate are annealed across
     generations.
  5. Optionally re-evaluate top performers on a fresh seed to detect
     "lucky-seed" champions before they pollute the elite pool.

Logging:
  * `logs/training.csv` — per-generation best / mean / worst / median
  * `checkpoints/best.keras` — current overall champion (overwritten)
  * `checkpoints/best_gen{N}.npz` — snapshot at milestone generations
"""
from __future__ import annotations

import csv
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
import keras

from game.engine import NeonHighwayEnv
from nn.model import (
    build_model,
    clone_weights,
    gaussian_mutate,
    predict_action,
    randomize_model,
    set_weights_into,
    uniform_crossover,
)
from nn.observe import observe


# ----------------------------------------------------------------- Genome
@dataclass
class Genome:
    model: keras.Model
    fitness: float = 0.0
    score: int = 0
    frames: int = 0
    level: int = 1


def make_initial_population(n: int, rng: np.random.Generator) -> List[Genome]:
    pop = []
    for _ in range(n):
        m = build_model()
        randomize_model(m, rng)
        pop.append(Genome(model=m))
    return pop


# -------------------------------------------------------------- Evaluation
def evaluate(
    genome: Genome,
    seed: int,
    max_frames: int,
) -> None:
    env = NeonHighwayEnv(seed=seed, max_frames=max_frames)
    while not env.done:
        obs = observe(env)
        action = predict_action(genome.model, obs)
        env.step(action)
    genome.fitness = env.fitness()
    genome.score = int(env.score)
    genome.frames = env._frames_alive
    genome.level = env._level_reached


# ----------------------------------------------------------------- Trainer
@dataclass
class TrainConfig:
    population_size: int = 60
    generations: int = 100
    elites: int = 4
    breeding_pool: int = 12  # top-K used as parents
    initial_mutation_rate: float = 0.08
    final_mutation_rate: float = 0.02
    initial_sigma: float = 0.12
    final_sigma: float = 0.02
    max_frames_per_episode: int = 60 * 180  # 3 game-minutes hard cap
    seed: int = 1337
    checkpoint_every: int = 10
    out_dir: str = "."
    early_stop_plateau: int = 30  # gens without best-fitness improvement → stop


def _anneal(start: float, end: float, t: float) -> float:
    """Linear schedule, t in [0,1]."""
    return start + (end - start) * t


def train(cfg: TrainConfig, chart_callback=None) -> Genome:
    """
    Returns the all-time best genome. `chart_callback(stats)` is invoked
    after each generation with a dict of per-gen stats — see viz/live_chart.py.
    """
    rng = np.random.default_rng(cfg.seed)
    random.seed(cfg.seed)

    out_dir = Path(cfg.out_dir)
    checkpoints = out_dir / "checkpoints"
    logs = out_dir / "logs"
    checkpoints.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)
    log_path = logs / "training.csv"
    with log_path.open("w", newline="") as f:
        csv.writer(f).writerow(
            ["generation", "best", "mean", "median", "worst",
             "best_score", "best_level", "best_frames", "elapsed_s"]
        )

    pop = make_initial_population(cfg.population_size, rng)
    all_time_best: Optional[Genome] = None
    plateau = 0

    t_start = time.time()
    for gen in range(1, cfg.generations + 1):
        seed_for_gen = cfg.seed + gen  # all genomes face the same world this gen

        for g in pop:
            evaluate(g, seed=seed_for_gen, max_frames=cfg.max_frames_per_episode)

        pop.sort(key=lambda g: g.fitness, reverse=True)
        fits = np.array([g.fitness for g in pop])
        best = pop[0]
        stats = {
            "generation": gen,
            "best": float(fits.max()),
            "mean": float(fits.mean()),
            "median": float(np.median(fits)),
            "worst": float(fits.min()),
            "best_score": best.score,
            "best_level": best.level,
            "best_frames": best.frames,
            "elapsed_s": time.time() - t_start,
        }
        with log_path.open("a", newline="") as f:
            csv.writer(f).writerow(
                [stats[k] for k in
                 ("generation", "best", "mean", "median", "worst",
                  "best_score", "best_level", "best_frames", "elapsed_s")]
            )
        print(
            f"[gen {gen:3d}] best={stats['best']:8.1f}  mean={stats['mean']:7.1f}  "
            f"median={stats['median']:7.1f}  score={best.score}  "
            f"level={best.level}  frames={best.frames}  "
            f"t={stats['elapsed_s']:.1f}s"
        )

        if chart_callback is not None:
            chart_callback(stats)

        improved = (all_time_best is None) or (best.fitness > all_time_best.fitness)
        if improved:
            all_time_best = Genome(
                model=build_model(),
                fitness=best.fitness, score=best.score,
                frames=best.frames, level=best.level,
            )
            set_weights_into(all_time_best.model, clone_weights(best.model))
            all_time_best.model.save(str(checkpoints / "best.keras"))
            plateau = 0
        else:
            plateau += 1
            if plateau >= cfg.early_stop_plateau:
                print(f"[early-stop] no improvement in {plateau} gens — halting")
                break

        if gen % cfg.checkpoint_every == 0:
            np.savez(
                checkpoints / f"best_gen{gen:04d}.npz",
                *clone_weights(best.model),
            )

        # Breed next generation
        pop = _breed_next(pop, cfg, gen, rng)

    return all_time_best


def _breed_next(
    pop: List[Genome],
    cfg: TrainConfig,
    gen: int,
    rng: np.random.Generator,
) -> List[Genome]:
    t = (gen - 1) / max(cfg.generations - 1, 1)
    mut_rate = _anneal(cfg.initial_mutation_rate, cfg.final_mutation_rate, t)
    sigma = _anneal(cfg.initial_sigma, cfg.final_sigma, t)

    parents = pop[: cfg.breeding_pool]
    next_pop: List[Genome] = []

    # Elites passed through unchanged (preserve best)
    for elite in pop[: cfg.elites]:
        clone = build_model()
        set_weights_into(clone, clone_weights(elite.model))
        next_pop.append(Genome(model=clone))

    # Children fill the rest
    while len(next_pop) < cfg.population_size:
        a, b = random.sample(parents, 2)
        crossed = uniform_crossover(
            clone_weights(a.model), clone_weights(b.model), rng
        )
        mutated = gaussian_mutate(crossed, mut_rate, sigma, rng)
        child = build_model()
        set_weights_into(child, mutated)
        next_pop.append(Genome(model=child))

    return next_pop
