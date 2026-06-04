"""Synthesize a soft, generic ambient pad for the walkthrough video.

No samples, no licensing, no deps beyond the stdlib: builds a slow 8-chord pad
(I-vi-IV-V in C, twice) with detuned sines, gentle per-chord swells, a sustained
bass, a faint high shimmer, a one-pole low-pass to take the edge off, a small
comb reverb for space, and an overall fade in/out. Writes a 44.1 kHz stereo WAV.

    uv run python -m scripts.make_music                 # -> video/public/music.wav
    uv run python -m scripts.make_music 60 out.wav      # custom length / path
"""
from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

SR = 44100
ROOT = "video/public/music.wav"

# (bass_hz, [triad_hz]) per chord — C major, A minor, F major, G major.
C = (65.41, [261.63, 329.63, 392.00])
Am = (110.0, [220.00, 261.63, 329.63])
F = (87.31, [174.61, 220.00, 261.63])
G = (98.00, [196.00, 246.94, 293.66])
PROG = [C, Am, F, G, C, Am, F, G]


def _note(t: float, f: float) -> float:
    # Two slightly detuned partials = soft chorus; a quiet octave for body.
    return 0.6 * math.sin(2 * math.pi * f * t) + 0.4 * math.sin(2 * math.pi * f * 1.003 * t) + 0.15 * math.sin(2 * math.pi * f * 2 * t)


def synth(seconds: float) -> list[float]:
    n = int(seconds * SR)
    seg = n / len(PROG)
    raw = [0.0] * n
    for i in range(n):
        t = i / SR
        si = min(len(PROG) - 1, int(i / seg))
        bass_hz, triad = PROG[si]
        # raised-cosine swell within the chord -> 0 at edges (no clicks), peak mid.
        local = (i - si * seg) / seg
        win = 0.5 - 0.5 * math.cos(2 * math.pi * local)
        chord = sum(_note(t, f) for f in triad) / len(triad)
        bass = math.sin(2 * math.pi * bass_hz * t) * 0.5
        # faint high shimmer with slow tremolo
        shimmer = math.sin(2 * math.pi * triad[0] * 2 * t) * 0.06 * (0.5 + 0.5 * math.sin(2 * math.pi * 0.15 * t))
        raw[i] = (chord * 0.6 + bass * 0.4) * win + shimmer
    return raw


def lowpass(x: list[float], a: float = 0.22) -> list[float]:
    y = [0.0] * len(x)
    prev = 0.0
    for i, v in enumerate(x):
        prev = prev + a * (v - prev)
        y[i] = prev
    return y


def reverb(x: list[float]) -> list[float]:
    d1, d2 = int(0.071 * SR), int(0.113 * SR)
    y = list(x)
    for i in range(len(x)):
        if i >= d1:
            y[i] += 0.28 * x[i - d1]
        if i >= d2:
            y[i] += 0.18 * x[i - d2]
    return y


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 54.0
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(ROOT)
    out.parent.mkdir(parents=True, exist_ok=True)

    sig = reverb(lowpass(synth(seconds)))
    n = len(sig)

    # normalize to -3 dBFS, then fade in 1.5 s / out 2.5 s.
    peak = max(1e-9, max(abs(v) for v in sig))
    g = 0.7 / peak
    fi, fo = int(1.5 * SR), int(2.5 * SR)
    frames = bytearray()
    for i, v in enumerate(sig):
        s = v * g
        if i < fi:
            s *= i / fi
        if i > n - fo:
            s *= max(0.0, (n - i) / fo)
        iv = max(-32767, min(32767, int(s * 32767)))
        frames += struct.pack("<hh", iv, iv)  # stereo (same L/R)

    with wave.open(str(out), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))
    print(f"wrote {out}  ({n / SR:.1f}s, {len(frames) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
