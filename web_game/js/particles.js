import * as THREE from 'three';
import { car } from './player.js';
import { scene } from './scene.js';
import { state } from './state.js';

// ── Particle Trail ──────────────────────────────────────────────
const POOL_SIZE   = 80;
const LIFETIME    = 0.45;  // seconds per particle
const SPREAD_X    = 0.6;
const SPREAD_Y    = 0.3;
const DRIFT_Z     = 8;    // backward drift speed

const positions  = new Float32Array(POOL_SIZE * 3);
const velocities = new Float32Array(POOL_SIZE * 3);
const lifetimes  = new Float32Array(POOL_SIZE);   // remaining life
const alphas     = new Float32Array(POOL_SIZE);
let   headIdx    = 0;

let points;
let particleMat;

export function buildParticles() {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));

  particleMat = new THREE.PointsMaterial({
    color: 0xff00ff,
    size: 0.18,
    transparent: true,
    opacity: 0.8,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    sizeAttenuation: true,
  });

  points = new THREE.Points(geo, particleMat);
  points.frustumCulled = false;
  scene.add(points);
}

export function setParticleColor(hexColor) {
  if (particleMat) particleMat.color.set(hexColor);
}

export function tickParticles(dt) {
  if (!points) return;

  // Emit new particles — rate scales with speed
  const emitCount = Math.ceil((state.speed / 80) * 3);
  for (let e = 0; e < emitCount; e++) {
    const i  = headIdx % POOL_SIZE;
    const i3 = i * 3;
    positions[i3]     = car.position.x + (Math.random() - 0.5) * SPREAD_X;
    positions[i3 + 1] = car.position.y - 0.1 + Math.random() * SPREAD_Y;
    positions[i3 + 2] = car.position.z + 2.0 + Math.random() * 0.5;
    velocities[i3]     = (Math.random() - 0.5) * 1.5;
    velocities[i3 + 1] = (Math.random() - 0.3) * 1.0;
    velocities[i3 + 2] = DRIFT_Z + Math.random() * 3;
    lifetimes[i] = LIFETIME;
    headIdx++;
  }

  // Update all particles
  for (let i = 0; i < POOL_SIZE; i++) {
    if (lifetimes[i] <= 0) {
      alphas[i] = 0;
      // Park dead particles off-screen
      positions[i * 3 + 1] = -100;
      continue;
    }
    lifetimes[i] -= dt;
    const i3 = i * 3;
    positions[i3]     += velocities[i3]     * dt;
    positions[i3 + 1] += velocities[i3 + 1] * dt;
    positions[i3 + 2] += velocities[i3 + 2] * dt;
    alphas[i] = Math.max(0, lifetimes[i] / LIFETIME);
  }

  // Global opacity = average of living particles (approximation — looks fine)
  particleMat.opacity = 0.85;
  points.geometry.attributes.position.needsUpdate = true;
}

// ── Speed Lines (2D canvas overlay) ─────────────────────────────
const SPEED_THRESHOLD = 50;
const MAX_LINES       = 25;

let slCanvas, slCtx;
const lines = [];  // persistent line objects for smooth animation

// ── Warp effect state ───────────────────────────────────────────
const WARP_LINES      = 120;
let warpActive        = false;
let warpElapsed       = 0;
let warpDuration      = 1.5;
const warpLines       = [];

class WarpLine {
  constructor() { this.reset(); }
  reset() {
    const angle   = Math.random() * Math.PI * 2;
    this.angle    = angle;
    this.radius   = 0.05 + Math.random() * 0.15;  // start close to center
    this.length   = 0.12 + Math.random() * 0.35;
    this.speed    = 0.8 + Math.random() * 1.5;
    this.width    = 0.5 + Math.random() * 2.5;
    this.hue      = 180 + Math.random() * 60;      // cyan-ish
  }
}

export function triggerWarp(duration = 1.5) {
  warpActive  = true;
  warpElapsed = 0;
  warpDuration = duration;
  warpLines.length = 0;
  for (let i = 0; i < WARP_LINES; i++) {
    const l = new WarpLine();
    l.radius += Math.random() * 0.6; // stagger initial radii
    warpLines.push(l);
  }
}

class SpeedLine {
  constructor() { this.reset(); }
  reset() {
    // Pick a random edge: 0=top, 1=bottom, 2=left, 3=right
    this.edge = Math.floor(Math.random() * 4);
    this.pos  = Math.random();           // position along that edge (0-1)
    this.len  = 0.08 + Math.random() * 0.15; // length as fraction of screen
    this.progress = 0;                   // 0 = at edge, 1 = reached center
    this.speed = 0.6 + Math.random() * 1.2;
    this.width = 0.5 + Math.random() * 1.5;
  }
}

export function initSpeedLines() {
  slCanvas = document.getElementById('speed-lines');
  if (!slCanvas) return;
  slCtx = slCanvas.getContext('2d');
  resizeSpeedCanvas();
  window.addEventListener('resize', resizeSpeedCanvas);

  for (let i = 0; i < MAX_LINES; i++) {
    const l = new SpeedLine();
    l.progress = Math.random(); // stagger initial positions
    lines.push(l);
  }
}

function resizeSpeedCanvas() {
  if (!slCanvas) return;
  slCanvas.width  = window.innerWidth;
  slCanvas.height = window.innerHeight;
}

export function tickSpeedLines(dt) {
  if (!slCtx) return;

  const w = slCanvas.width;
  const h = slCanvas.height;
  const cx = w * 0.5;
  const cy = h * 0.45;

  // ── Warp effect (overrides normal speed lines while active) ──
  if (warpActive) {
    warpElapsed += dt;
    const t = Math.min(warpElapsed / warpDuration, 1);

    slCtx.clearRect(0, 0, w, h);

    // Vignette / radial darkening
    const vigAlpha = 0.3 * (1 - t);
    const grad = slCtx.createRadialGradient(cx, cy, w * 0.15, cx, cy, w * 0.7);
    grad.addColorStop(0, 'rgba(0,0,0,0)');
    grad.addColorStop(1, `rgba(0,0,0,${vigAlpha})`);
    slCtx.fillStyle = grad;
    slCtx.fillRect(0, 0, w, h);

    // Central glow
    const glowAlpha = 0.25 * (1 - t);
    const glow = slCtx.createRadialGradient(cx, cy, 0, cx, cy, w * 0.12);
    glow.addColorStop(0, `rgba(0,255,255,${glowAlpha})`);
    glow.addColorStop(1, 'rgba(0,255,255,0)');
    slCtx.fillStyle = glow;
    slCtx.fillRect(0, 0, w, h);

    // Streak lines radiating from center
    for (const l of warpLines) {
      l.radius += l.speed * dt;
      if (l.radius > 1.5) l.reset();

      const fadeIn  = Math.min(l.radius / 0.2, 1);
      const fadeOut = Math.max(0, 1 - (l.radius - 0.5));
      const alpha   = fadeIn * fadeOut * (1 - t * 0.6) * 0.7;
      if (alpha <= 0.01) continue;

      const cos = Math.cos(l.angle);
      const sin = Math.sin(l.angle);
      const r1  = l.radius * w * 0.5;
      const r2  = (l.radius + l.length) * w * 0.5;

      slCtx.beginPath();
      slCtx.moveTo(cx + cos * r1, cy + sin * r1);
      slCtx.lineTo(cx + cos * r2, cy + sin * r2);
      slCtx.strokeStyle = `hsla(${l.hue}, 100%, 75%, ${alpha})`;
      slCtx.lineWidth   = l.width;
      slCtx.stroke();
    }

    if (t >= 1) warpActive = false;
    return;
  }

  // ── Normal speed lines ────────────────────────────────────────
  const intensity = Math.max(0, (state.speed - SPEED_THRESHOLD) / 30);
  slCtx.clearRect(0, 0, w, h);
  if (intensity <= 0 || state.phase !== 'playing') return;

  for (const l of lines) {
    l.progress += l.speed * dt;
    if (l.progress >= 1) l.reset();

    const alpha = intensity * (1 - l.progress) * 0.5;
    if (alpha <= 0.01) continue;

    let sx, sy;
    switch (l.edge) {
      case 0: sx = l.pos * w; sy = 0;     break;
      case 1: sx = l.pos * w; sy = h;     break;
      case 2: sx = 0;         sy = l.pos * h; break;
      case 3: sx = w;         sy = l.pos * h; break;
    }

    const ex = sx + (cx - sx) * l.progress * l.len * 3;
    const ey = sy + (cy - sy) * l.progress * l.len * 3;

    slCtx.beginPath();
    slCtx.moveTo(sx, sy);
    slCtx.lineTo(ex, ey);
    slCtx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
    slCtx.lineWidth   = l.width;
    slCtx.stroke();
  }
}
