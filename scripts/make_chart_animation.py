"""
Render an animated fitness chart from a training.csv as a standalone MP4.

The chart mirrors the live training chart in `viz/live_chart.py` — twin-axis
matplotlib figure with best/median/mean/worst fitness lines plus best raw
score on a secondary axis — but reveals one generation at a time so it can
be embedded into the evolution video as a "training progress" segment.

Usage:
    python scripts/make_chart_animation.py \
        --csv training_run_2026-05-14/training.csv \
        --out chart.mp4 \
        --duration 20 --fps 30
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter, FuncAnimation


VIDEO_W = 1280
VIDEO_H = 800

# Match viz/live_chart.py palette so the embedded chart feels continuous
# with the chart shown while training was running live.
COLOR_BEST = "#00ffaa"
COLOR_MEDIAN = "#ffaa00"
COLOR_MEAN = "#aa88ff"
COLOR_WORST = "#ff4466"
COLOR_SCORE = "#66ddff"
COLOR_BG = "#0a0a14"
COLOR_GRID = "#222233"
COLOR_TEXT = "#e8e8f0"


def _load_csv(path: Path) -> Dict[str, List[float]]:
    cols: Dict[str, List[float]] = {
        "generation": [], "best": [], "mean": [],
        "median": [], "worst": [], "best_score": [],
        "best_level": [], "best_frames": [],
    }
    with path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            for k in cols:
                cols[k].append(float(row[k]))
    return cols


def render(csv_path: Path, out_path: Path, duration_s: float, fps: int) -> None:
    data = _load_csv(csv_path)
    n_gens = len(data["generation"])
    if n_gens == 0:
        raise SystemExit(f"empty csv: {csv_path}")

    total_frames = int(duration_s * fps)
    hold_frames = int(2.5 * fps)              # freeze on final state for 2.5s
    reveal_frames = max(1, total_frames - hold_frames)

    fig = plt.figure(figsize=(VIDEO_W / 100, VIDEO_H / 100), dpi=100,
                     facecolor=COLOR_BG)
    ax_fit = fig.add_subplot(111)
    ax_score = ax_fit.twinx()

    for ax in (ax_fit, ax_score):
        ax.set_facecolor(COLOR_BG)
        for spine in ax.spines.values():
            spine.set_color(COLOR_GRID)
        ax.tick_params(colors=COLOR_TEXT)

    ax_fit.set_xlabel("generation", color=COLOR_TEXT, fontsize=13)
    ax_fit.set_ylabel("fitness", color=COLOR_TEXT, fontsize=13)
    ax_score.set_ylabel("best score (game points)",
                        color=COLOR_TEXT, fontsize=13)
    ax_fit.grid(True, alpha=0.25, color=COLOR_GRID)

    fig.suptitle("Neon Highway · GA training progress",
                 color=COLOR_TEXT, fontsize=18, fontweight="bold")

    # Final axis limits picked up front so the camera doesn't pop as new
    # generations come in — the reveal happens via line data, not autoscale.
    x_max = max(data["generation"]) * 1.02
    fit_min = min(min(data["worst"]), 0) * 1.05
    fit_max = max(data["best"]) * 1.08
    score_max = max(data["best_score"]) * 1.08
    ax_fit.set_xlim(0, x_max)
    ax_fit.set_ylim(fit_min, fit_max)
    ax_score.set_ylim(0, score_max)

    (line_best,) = ax_fit.plot([], [], color=COLOR_BEST,
                               label="best", linewidth=2.5)
    (line_median,) = ax_fit.plot([], [], color=COLOR_MEDIAN,
                                 label="median", linewidth=1.6)
    (line_mean,) = ax_fit.plot([], [], color=COLOR_MEAN,
                               label="mean", linewidth=1.1, linestyle="--")
    (line_worst,) = ax_fit.plot([], [], color=COLOR_WORST,
                                label="worst", linewidth=0.9, alpha=0.7)
    (line_score,) = ax_score.plot([], [], color=COLOR_SCORE,
                                  label="best score", linewidth=1.2,
                                  alpha=0.85)

    leg1 = ax_fit.legend(loc="upper left", facecolor=COLOR_BG,
                         edgecolor=COLOR_GRID, labelcolor=COLOR_TEXT)
    leg2 = ax_score.legend(loc="upper right", facecolor=COLOR_BG,
                           edgecolor=COLOR_GRID, labelcolor=COLOR_TEXT)
    for leg in (leg1, leg2):
        for txt in leg.get_texts():
            txt.set_color(COLOR_TEXT)

    info_text = ax_fit.text(
        0.5, 0.94, "", transform=ax_fit.transAxes,
        ha="center", va="top", color=COLOR_TEXT, fontsize=14,
        fontweight="bold",
        bbox=dict(facecolor="#101020", edgecolor=COLOR_GRID,
                  boxstyle="round,pad=0.4", alpha=0.85),
    )

    fig.tight_layout(rect=(0, 0, 1, 0.95))

    def frame(i: int):
        if i < reveal_frames:
            n = max(1, int((i + 1) / reveal_frames * n_gens))
        else:
            n = n_gens
        xs = data["generation"][:n]
        line_best.set_data(xs, data["best"][:n])
        line_median.set_data(xs, data["median"][:n])
        line_mean.set_data(xs, data["mean"][:n])
        line_worst.set_data(xs, data["worst"][:n])
        line_score.set_data(xs, data["best_score"][:n])

        gen_now = int(data["generation"][n - 1])
        best_now = data["best"][n - 1]
        score_now = data["best_score"][n - 1]
        level_now = int(data["best_level"][n - 1])
        info_text.set_text(
            f"gen {gen_now:>3}  ·  best fitness {best_now:,.0f}  "
            f"·  score {score_now:,.0f}  ·  level {level_now}"
        )
        return (line_best, line_median, line_mean, line_worst,
                line_score, info_text)

    anim = FuncAnimation(
        fig, frame, frames=total_frames,
        interval=1000 / fps, blit=False, repeat=False,
    )

    writer = FFMpegWriter(
        fps=fps, codec="libx264",
        bitrate=4000,
        extra_args=["-pix_fmt", "yuv420p", "-preset", "fast"],
    )
    print(f"[chart-anim] rendering {total_frames} frames "
          f"({duration_s}s @ {fps}fps) → {out_path}")
    anim.save(str(out_path), writer=writer)
    plt.close(fig)
    print(f"[chart-anim] ✓ wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True,
                    help="path to training.csv")
    ap.add_argument("--out", required=True,
                    help="output mp4 path")
    ap.add_argument("--duration", type=float, default=20.0,
                    help="total clip duration in seconds")
    ap.add_argument("--fps", type=int, default=30)
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        raise SystemExit(f"csv not found: {csv_path}")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    render(csv_path, out_path, args.duration, args.fps)


if __name__ == "__main__":
    main()
