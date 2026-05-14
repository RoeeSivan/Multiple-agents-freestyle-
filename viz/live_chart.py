"""
Live matplotlib fitness chart, updated once per generation.

Two axes:
  * Left  — fitness lines: best, median, mean, worst.
  * Right — score of the best genome (raw game score, ignoring fitness
            shaping). Useful to confirm "fitness goes up" actually means
            "agents play better".

Call .update(stats) from inside the GA training loop. Stats keys come
from ga/train.py's `stats` dict.
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import matplotlib

matplotlib.use("TkAgg")  # interactive backend that works on macOS without IPython
import matplotlib.pyplot as plt


class LiveChart:
    def __init__(self, title: str = "Neon Highway · GA training"):
        plt.ion()
        self.fig, self.ax_fit = plt.subplots(figsize=(9, 5))
        self.ax_score = self.ax_fit.twinx()

        self.gens: List[int] = []
        self.best: List[float] = []
        self.mean: List[float] = []
        self.median: List[float] = []
        self.worst: List[float] = []
        self.score: List[float] = []

        (self.line_best,) = self.ax_fit.plot([], [], color="#00ffaa",
                                             label="best", linewidth=2)
        (self.line_median,) = self.ax_fit.plot([], [], color="#ffaa00",
                                               label="median", linewidth=1.5)
        (self.line_mean,) = self.ax_fit.plot([], [], color="#aa88ff",
                                             label="mean", linewidth=1.0,
                                             linestyle="--")
        (self.line_worst,) = self.ax_fit.plot([], [], color="#ff4466",
                                              label="worst", linewidth=0.8,
                                              alpha=0.6)
        (self.line_score,) = self.ax_score.plot([], [], color="#66ddff",
                                                label="best score",
                                                linewidth=1.0, alpha=0.7)

        self.fig.suptitle(title, color="#222")
        self.ax_fit.set_xlabel("generation")
        self.ax_fit.set_ylabel("fitness")
        self.ax_score.set_ylabel("best score (game points)")
        self.ax_fit.grid(True, alpha=0.3)
        self.ax_fit.legend(loc="upper left")
        self.ax_score.legend(loc="upper right")
        self.fig.tight_layout()

    def update(self, stats: dict, save_path: Path | None = None) -> None:
        self.gens.append(stats["generation"])
        self.best.append(stats["best"])
        self.mean.append(stats["mean"])
        self.median.append(stats["median"])
        self.worst.append(stats["worst"])
        self.score.append(stats["best_score"])

        self.line_best.set_data(self.gens, self.best)
        self.line_mean.set_data(self.gens, self.mean)
        self.line_median.set_data(self.gens, self.median)
        self.line_worst.set_data(self.gens, self.worst)
        self.line_score.set_data(self.gens, self.score)

        self.ax_fit.relim(); self.ax_fit.autoscale_view()
        self.ax_score.relim(); self.ax_score.autoscale_view()

        self.fig.canvas.draw_idle()
        self.fig.canvas.flush_events()

        if save_path is not None:
            self.fig.savefig(save_path, dpi=110, facecolor="white")

    def hold(self) -> None:
        """Block once training is done, so the final chart stays visible."""
        plt.ioff()
        plt.show()
