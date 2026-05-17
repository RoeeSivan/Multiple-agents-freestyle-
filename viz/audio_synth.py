"""
Numpy port of web_game/js/audio.js — synthesises the original game's sounds
offline so replay videos can carry the same audio as the live browser game.

Every function returns a mono float32 ndarray at 44.1 kHz. Parameters match
the Web Audio API oscillator/gain configurations in audio.js verbatim.
"""
from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Union

import numpy as np

SAMPLE_RATE = 44100


def _t(n_samples: int, sr: int = SAMPLE_RATE) -> np.ndarray:
    return np.arange(n_samples, dtype=np.float64) / sr


def _sine(t: np.ndarray, freq: float) -> np.ndarray:
    return np.sin(2.0 * np.pi * freq * t)


def _square(t: np.ndarray, freq: float) -> np.ndarray:
    return np.sign(_sine(t, freq))


def _sawtooth(t: np.ndarray, freq: float) -> np.ndarray:
    return 2.0 * (t * freq - np.floor(t * freq + 0.5))


def _exp_freq_sweep(t: np.ndarray, f0: float, f1: float, duration: float) -> np.ndarray:
    """Phase integral of exponential frequency sweep f(t) = f0 * (f1/f0)**(t/duration)."""
    if f0 == f1:
        return 2.0 * np.pi * f0 * t
    k = np.log(f1 / f0) / duration
    return 2.0 * np.pi * f0 * (np.exp(k * t) - 1.0) / k


def _exp_ramp(t: np.ndarray, v0: float, v1: float, duration: float) -> np.ndarray:
    v0 = max(v0, 1e-9)
    v1 = max(v1, 1e-9)
    return v0 * (v1 / v0) ** (t / duration)


_NOISE_RNG = np.random.default_rng(20260516)


def _white_noise(n: int) -> np.ndarray:
    return _NOISE_RNG.uniform(-1.0, 1.0, size=n)


def synth_melody_note(freq: float, sr: int = SAMPLE_RATE) -> np.ndarray:
    """audio.js:29-41 — sine wave, gain 0.45 → 0.001 exp over 0.35 s."""
    duration = 0.35
    n = int(duration * sr)
    t = _t(n, sr)
    env = _exp_ramp(t, 0.45, 0.001, duration)
    return (np.sin(2.0 * np.pi * freq * t) * env).astype(np.float32)


def synth_laser_shoot(sr: int = SAMPLE_RATE) -> np.ndarray:
    """audio.js:43-57 — square 880→220 Hz, gain 0.3→0.001 over 0.15 s."""
    duration = 0.15
    n = int(duration * sr)
    t = _t(n, sr)
    phase = _exp_freq_sweep(t, 880.0, 220.0, duration)
    wave_ = np.sign(np.sin(phase))
    env = _exp_ramp(t, 0.3, 0.001, duration)
    return (wave_ * env).astype(np.float32)


def synth_laser_hit(sr: int = SAMPLE_RATE) -> np.ndarray:
    """audio.js:59-87 — sawtooth 200→60 Hz @ 0.7→0.001 over 0.25 s + noise 0.12 s."""
    duration = 0.25
    n = int(duration * sr)
    t = _t(n, sr)
    phase = _exp_freq_sweep(t, 200.0, 60.0, duration)
    saw_phase = phase / (2.0 * np.pi)
    saw_wave = 2.0 * (saw_phase - np.floor(saw_phase + 0.5))
    saw_env = _exp_ramp(t, 0.7, 0.001, duration)
    out = saw_wave * saw_env

    noise_duration = 0.12
    noise_n = int(noise_duration * sr)
    t_n = _t(noise_n, sr)
    noise_env = _exp_ramp(t_n, 0.4, 0.001, noise_duration)
    out[:noise_n] += _white_noise(noise_n) * noise_env
    return out.astype(np.float32)


def synth_coin(sr: int = SAMPLE_RATE) -> np.ndarray:
    """audio.js:89-103 — sine 1200→1800 Hz over 0.08 s, gain 0.3→0.001 over 0.12 s."""
    total_duration = 0.12
    n = int(total_duration * sr)
    t = _t(n, sr)
    # Web Audio: freq sweeps 1200→1800 over 0.08s, then holds at 1800 for 0.04s.
    sweep_duration = 0.08
    phase = np.empty(n)
    sweep_n = int(sweep_duration * sr)
    if sweep_n > 0:
        t_sweep = _t(sweep_n, sr)
        phase[:sweep_n] = _exp_freq_sweep(t_sweep, 1200.0, 1800.0, sweep_duration)
    if sweep_n < n:
        last_phase = phase[sweep_n - 1] if sweep_n > 0 else 0.0
        t_tail = _t(n - sweep_n, sr)
        phase[sweep_n:] = last_phase + 2.0 * np.pi * 1800.0 * t_tail
    wave_ = np.sin(phase)
    env = _exp_ramp(t, 0.3, 0.001, total_duration)
    return (wave_ * env).astype(np.float32)


def synth_collision(sr: int = SAMPLE_RATE) -> np.ndarray:
    """audio.js:163-193 — sawtooth 120→30 Hz @ 1.0→0.001 over 0.2 s + noise 0.18 s @ 0.55."""
    duration = 0.2
    n = int(duration * sr)
    t = _t(n, sr)
    phase = _exp_freq_sweep(t, 120.0, 30.0, duration)
    saw_phase = phase / (2.0 * np.pi)
    saw_wave = 2.0 * (saw_phase - np.floor(saw_phase + 0.5))
    saw_env = _exp_ramp(t, 1.0, 0.001, duration)
    out = saw_wave * saw_env

    noise_duration = 0.18
    noise_n = int(noise_duration * sr)
    t_n = _t(noise_n, sr)
    noise_env = _exp_ramp(t_n, 0.55, 0.001, noise_duration)
    out[:noise_n] += _white_noise(noise_n) * noise_env
    return out.astype(np.float32)


def synth_warp(sr: int = SAMPLE_RATE) -> np.ndarray:
    """audio.js:105-161 — 3-layer 1.5 s warp. Not used by Python engine; kept
    for completeness in case future hooks add warp events."""
    duration = 1.5
    n = int(duration * sr)
    t = _t(n, sr)

    # Layer 1: sine 200→2000 (0..0.7*dur), then 2000→800 (0.7*dur..dur)
    seg1 = 0.7 * duration
    seg2 = duration - seg1
    n1 = int(seg1 * sr)
    n2 = n - n1
    t1 = _t(n1, sr)
    t2 = _t(n2, sr)
    phase1 = _exp_freq_sweep(t1, 200.0, 2000.0, seg1)
    last1 = phase1[-1] if n1 else 0.0
    phase2 = last1 + _exp_freq_sweep(t2, 2000.0, 800.0, seg2)
    phase = np.concatenate([phase1, phase2])
    wave1 = np.sin(phase)

    # Linear gain 0.25 → 0.4 over 0.3*dur, exp 0.4 → 0.001 to end
    g_seg1 = 0.3 * duration
    gn1 = int(g_seg1 * sr)
    gn2 = n - gn1
    gain1 = np.linspace(0.25, 0.4, gn1, dtype=np.float64)
    tg2 = _t(gn2, sr)
    gain2 = _exp_ramp(tg2, 0.4, 0.001, duration - g_seg1)
    gain = np.concatenate([gain1, gain2])
    out = wave1 * gain

    # Layer 2: triangle (approx via 2 * |sawtooth| - 1) 400→4000 then 4000→1600
    phase1b = _exp_freq_sweep(t1, 400.0, 4000.0, seg1)
    last1b = phase1b[-1] if n1 else 0.0
    phase2b = last1b + _exp_freq_sweep(t2, 4000.0, 1600.0, seg2)
    phaseb = np.concatenate([phase1b, phase2b])
    saw_p = phaseb / (2.0 * np.pi)
    saw_w = 2.0 * (saw_p - np.floor(saw_p + 0.5))
    tri = 2.0 * np.abs(saw_w) - 1.0
    gain1b = np.linspace(0.12, 0.2, gn1, dtype=np.float64)
    gain2b = _exp_ramp(tg2, 0.2, 0.001, duration - g_seg1)
    gainb = np.concatenate([gain1b, gain2b])
    out += tri * gainb

    # Layer 3: noise (no bandpass filter — too costly to port; reasonable
    # to leave broadband for short warp burst). Volume mirrors audio.js.
    n_seg1 = 0.4 * duration
    nn1 = int(n_seg1 * sr)
    nn2 = n - nn1
    n_gain1 = np.linspace(0.15, 0.35, nn1, dtype=np.float64)
    n_tg = _t(nn2, sr)
    n_gain2 = _exp_ramp(n_tg, 0.35, 0.001, duration - n_seg1)
    n_gain = np.concatenate([n_gain1, n_gain2])
    out += _white_noise(n) * n_gain

    return out.astype(np.float32)


class Mixer:
    """Sparse offline mixdown to a single float32 mono buffer."""

    def __init__(self, duration_s: float, sr: int = SAMPLE_RATE):
        self.sr = sr
        self.n = int(np.ceil(duration_s * sr))
        self.buffer = np.zeros(self.n, dtype=np.float32)

    def add(self, t_seconds: float, samples: np.ndarray) -> None:
        start = int(t_seconds * self.sr)
        if start >= self.n:
            return
        end = min(start + samples.shape[0], self.n)
        length = end - start
        if length <= 0:
            return
        self.buffer[start:end] += samples[:length]

    def to_wav(self, path: Union[str, Path]) -> None:
        peak = float(np.max(np.abs(self.buffer))) if self.n else 0.0
        scale = 1.0 / peak if peak > 1.0 else 1.0
        clipped = np.clip(self.buffer * scale, -1.0, 1.0)
        ints = (clipped * 32767.0).astype(np.int16)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sr)
            wf.writeframes(ints.tobytes())
