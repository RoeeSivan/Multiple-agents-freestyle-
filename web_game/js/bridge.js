// bridge.js — exposes game internals to window so an external script
// (Playwright / Selenium / DevTools console) can read state and drive
// the trained neural network against the real Three.js game.
//
// The original game keeps its state inside ES modules and never touches
// the global window object. This bridge imports those same modules — ES
// modules are singletons, so we get the exact live state object that
// main.js is mutating each frame, no copying involved.

import { state } from './state.js';
import { car } from './player.js';

window.gameState = function gameState() {
  return {
    phase: state.phase,
    score: state.score,
    lives: state.lives,
    lane: state.lane,
    speed: state.speed,
    level: state.level,
    elapsed: state.elapsed,
    combo: state.combo,
    shielded: !!state.shielded,
    boostActive: state.boostUntil > state.elapsed,
    jumpVelocity: state.jumpVelocity,
    jumpsUsed: state.jumpsUsed,
    player: {
      x: car ? car.position.x : 0,
      y: car ? car.position.y : 0,
      z: car ? car.position.z : 0,
    },
    blocks: state.blocks.map((b) => ({
      lane: b.lane,
      type: b.type,
      x: b.mesh.position.x,
      y: b.mesh.position.y,
      z: b.mesh.position.z,
      processed: !!b.processed,
    })),
    lasers: state.lasers.map((l) => ({
      x: l.mesh.position.x,
      y: l.mesh.position.y,
      z: l.mesh.position.z,
    })),
  };
};

// Diagnostic ping so the driver can verify the bridge loaded.
window.__bridgeReady = true;
console.log('[bridge] window.gameState() ready');
