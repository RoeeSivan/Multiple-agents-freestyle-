# Neon Highway × Genetic Algorithm

Train a neural network to play [Neon Highway](https://neonhighway.vercel.app/) using a genetic algorithm — MarI/O-style, but with a fixed-topology Keras MLP instead of NEAT.

The original Three.js game lives in `HW1/assignment1-exercise4/` (not modified). This project re-implements its mechanics in headless Python so we can simulate thousands of games per second for fitness evaluation, then replays the best evolved agent in a pygame renderer for the submission video.

Reference: assignment 3 exercise 3 (option 2, genetic algorithm). Inspired by [SethBling's MarI/O](https://www.youtube.com/watch?v=qv6UVOQ0F44) and [dk8827/flappy_nn](https://github.com/dk8827/flappy_nn).

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Sanity check: tiny GA, finishes in ~30s
python main.py smoke

# Play the Python clone yourself — verify it feels like the web game
python main.py human

# Real training (live chart + checkpoints)
python main.py train --pop 60 --gens 100 --hold

# Replay the best evolved agent
python main.py replay --genome checkpoints/best.keras

# Record an MP4 of the best agent
python main.py replay --genome checkpoints/best.keras --record out.mp4
```

## Layout

| Path | Purpose |
|---|---|
| `game/config.py` | All numerical constants — ported from `cfg.js` |
| `game/patterns.py` | The 12 obstacle spawn patterns |
| `game/engine.py` | Headless deterministic game (no rendering) |
| `game/renderer.py` | pygame top-down view, replay only |
| `nn/model.py` | Keras MLP factory + GA weight ops |
| `nn/observe.py` | Game state → 16-d feature vector |
| `ga/train.py` | Selection, crossover, mutation, training loop |
| `viz/live_chart.py` | Live matplotlib fitness chart |
| `replay/record.py` | Replay + MP4 recording |
| `main.py` | CLI entry point |

## Design choices

* **Keras NumPy backend** (`KERAS_BACKEND=numpy`) — no TF/GPU overhead, perfect for tiny GA-only nets.
* **Fixed-topology MLP** (16 → 24 → 16 → 4) — simpler than NEAT, fits Keras cleanly.
* **Game state vector**, not pixels — much faster than CNN-on-screenshot.
* **Deterministic per-generation seed** — every genome in one generation faces the same obstacle stream, so fitness comparisons are fair.
* **ms-based spawn accumulators** instead of real-time setInterval timers — matches the web game's spawn cadence in simulated time.
