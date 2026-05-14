// Web Audio API — melody notes, collision sound, and mute control.

let audioCtx   = null;
let masterGain = null;
let muted      = false;

export function ensureAudio() {
  if (audioCtx) {
    if (audioCtx.state === 'suspended') audioCtx.resume();
    return;
  }
  audioCtx   = new (window.AudioContext || window.webkitAudioContext)();
  masterGain = audioCtx.createGain();
  masterGain.gain.setValueAtTime(muted ? 0 : 1, audioCtx.currentTime);
  masterGain.connect(audioCtx.destination);
}

export function getMuted() { return muted; }

export function resetBeat() {}

// Toggles mute and returns the new muted state so callers can sync UI.
export function toggleMute() {
  muted = !muted;
  if (masterGain) masterGain.gain.setValueAtTime(muted ? 0 : 1, audioCtx.currentTime);
  return muted;
}

export function playMelodyNote(freq) {
  const t    = audioCtx.currentTime;
  const osc  = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type   = 'sine';
  osc.frequency.setValueAtTime(freq, t);
  gain.gain.setValueAtTime(0.45, t);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.35);
  osc.connect(gain);
  gain.connect(masterGain);
  osc.start(t);
  osc.stop(t + 0.35);
}

export function playLaserShootSound() {
  if (!audioCtx) return;
  const t = audioCtx.currentTime;
  const osc  = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type   = 'square';
  osc.frequency.setValueAtTime(880, t);
  osc.frequency.exponentialRampToValueAtTime(220, t + 0.15);
  gain.gain.setValueAtTime(0.3, t);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
  osc.connect(gain);
  gain.connect(masterGain);
  osc.start(t);
  osc.stop(t + 0.15);
}

export function playLaserHitSound() {
  if (!audioCtx) return;
  const t = audioCtx.currentTime;
  // Harsh buzz + static
  const osc  = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type   = 'sawtooth';
  osc.frequency.setValueAtTime(200, t);
  osc.frequency.exponentialRampToValueAtTime(60, t + 0.25);
  gain.gain.setValueAtTime(0.7, t);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
  osc.connect(gain);
  gain.connect(masterGain);
  osc.start(t);
  osc.stop(t + 0.25);

  const sampleRate = audioCtx.sampleRate;
  const buf  = audioCtx.createBuffer(1, Math.floor(sampleRate * 0.12), sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  const src       = audioCtx.createBufferSource();
  src.buffer      = buf;
  const noiseGain = audioCtx.createGain();
  noiseGain.gain.setValueAtTime(0.4, t);
  noiseGain.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
  src.connect(noiseGain);
  noiseGain.connect(masterGain);
  src.start(t);
}

export function playCoinSound() {
  if (!audioCtx) return;
  const t = audioCtx.currentTime;
  const osc  = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type   = 'sine';
  osc.frequency.setValueAtTime(1200, t);
  osc.frequency.exponentialRampToValueAtTime(1800, t + 0.08);
  gain.gain.setValueAtTime(0.3, t);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.12);
  osc.connect(gain);
  gain.connect(masterGain);
  osc.start(t);
  osc.stop(t + 0.12);
}

export function playWarpSound() {
  if (!audioCtx) return;
  const t = audioCtx.currentTime;
  const dur = 1.5;

  // Layer 1: rising sine sweep (200 Hz → 2000 Hz)
  const osc1  = audioCtx.createOscillator();
  const gain1 = audioCtx.createGain();
  osc1.type   = 'sine';
  osc1.frequency.setValueAtTime(200, t);
  osc1.frequency.exponentialRampToValueAtTime(2000, t + dur * 0.7);
  osc1.frequency.exponentialRampToValueAtTime(800, t + dur);
  gain1.gain.setValueAtTime(0.25, t);
  gain1.gain.linearRampToValueAtTime(0.4, t + dur * 0.3);
  gain1.gain.exponentialRampToValueAtTime(0.001, t + dur);
  osc1.connect(gain1);
  gain1.connect(masterGain);
  osc1.start(t);
  osc1.stop(t + dur);

  // Layer 2: detuned octave for thickness
  const osc2  = audioCtx.createOscillator();
  const gain2 = audioCtx.createGain();
  osc2.type   = 'triangle';
  osc2.frequency.setValueAtTime(400, t);
  osc2.frequency.exponentialRampToValueAtTime(4000, t + dur * 0.7);
  osc2.frequency.exponentialRampToValueAtTime(1600, t + dur);
  gain2.gain.setValueAtTime(0.12, t);
  gain2.gain.linearRampToValueAtTime(0.2, t + dur * 0.3);
  gain2.gain.exponentialRampToValueAtTime(0.001, t + dur);
  osc2.connect(gain2);
  gain2.connect(masterGain);
  osc2.start(t);
  osc2.stop(t + dur);

  // Layer 3: filtered noise whoosh
  const sampleRate = audioCtx.sampleRate;
  const buf  = audioCtx.createBuffer(1, Math.floor(sampleRate * dur), sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  const src       = audioCtx.createBufferSource();
  src.buffer      = buf;
  const bp        = audioCtx.createBiquadFilter();
  bp.type         = 'bandpass';
  bp.frequency.setValueAtTime(500, t);
  bp.frequency.exponentialRampToValueAtTime(4000, t + dur * 0.6);
  bp.frequency.exponentialRampToValueAtTime(800, t + dur);
  bp.Q.value      = 2;
  const noiseGain = audioCtx.createGain();
  noiseGain.gain.setValueAtTime(0.15, t);
  noiseGain.gain.linearRampToValueAtTime(0.35, t + dur * 0.4);
  noiseGain.gain.exponentialRampToValueAtTime(0.001, t + dur);
  src.connect(bp);
  bp.connect(noiseGain);
  noiseGain.connect(masterGain);
  src.start(t);
}

export function playCollisionSound() {
  if (!audioCtx) return;
  const t = audioCtx.currentTime;

  // Layer 1: deep sawtooth thud (120 Hz → 30 Hz sweep)
  const osc  = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.type   = 'sawtooth';
  osc.frequency.setValueAtTime(120, t);
  osc.frequency.exponentialRampToValueAtTime(30, t + 0.2);
  gain.gain.setValueAtTime(1.0, t);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.2);
  osc.connect(gain);
  gain.connect(masterGain);
  osc.start(t);
  osc.stop(t + 0.2);

  // Layer 2: full-range noise burst (no high-pass — keep the low crunch)
  const sampleRate = audioCtx.sampleRate;
  const buf  = audioCtx.createBuffer(1, Math.floor(sampleRate * 0.18), sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
  const src       = audioCtx.createBufferSource();
  src.buffer      = buf;
  const noiseGain = audioCtx.createGain();
  noiseGain.gain.setValueAtTime(0.55, t);
  noiseGain.gain.exponentialRampToValueAtTime(0.001, t + 0.18);
  src.connect(noiseGain);
  noiseGain.connect(masterGain);
  src.start(t);
}
