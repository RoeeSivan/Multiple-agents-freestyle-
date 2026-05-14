# Training Run · 2026-05-14

## Config
- Population: 60
- Generations: 100 (early-stopped at 81 — no improvement for 30 gens)
- Seed: 1337
- Episode cap: 60 × 180 frames (3 game-minutes)
- Architecture: 16 → 24 → 16 → 4 MLP, tanh hidden, Keras numpy backend

## Final result
- **Best ever fitness: 49980.2**
- Score: 48750 (raw game points)
- Level reached: 6 (max — game caps at level 6)
- Frames alive: 9802 (≈ 163 sec / 2.7 min of play)
- Wall-clock: ~75 min

## Files

| File | Purpose |
|---|---|
| `best.keras` | Champion model — load with `keras.models.load_model()` |
| `best_gen{N}.npz` | Generation snapshots (every 10 gens) for evolution comparison |
| `training.csv` | Per-generation stats (best/mean/median/worst/score/level/frames) |
| `fitness.png` | Live chart final state |

## Reproduce / replay

```bash
python main.py replay --genome training_run_2026-05-14/best.keras --record final.mp4
```

## Notes
- Early stop fired because agent hit level 6 (game's hardest level) and
  there's no further difficulty for it to break through.
- Best agent survives indefinitely at top speed (80 u/s, beat 275 ms),
  navigates the 12-pattern obstacle stream cleanly, builds combos for
  the 32× multiplier.
