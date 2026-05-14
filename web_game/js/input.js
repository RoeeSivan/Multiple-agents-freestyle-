// Phase-agnostic input module. Emits lane-change intents to registered callbacks.
// The caller (main.js) is responsible for any phase guards.

const laneChangeListeners = [];
const jumpListeners = [];

export function onLaneChange(fn) { laneChangeListeners.push(fn); }
export function onJump(fn)       { jumpListeners.push(fn); }

// ── Keyboard ──────────────────────────────────────────────────
const pressed = {};

document.addEventListener('keydown', e => {
  if (pressed[e.code]) return;
  pressed[e.code] = true;
  if (e.code === 'ArrowLeft'  || e.code === 'KeyA') emit(-1);
  if (e.code === 'ArrowRight' || e.code === 'KeyD') emit(+1);
  if (e.code === 'Space') {
    e.preventDefault(); // Prevent Space from triggering button clicks (e.g., mute button)
    jumpListeners.forEach(fn => fn());
  }
});

document.addEventListener('keyup', e => { pressed[e.code] = false; });

function emit(direction) {
  laneChangeListeners.forEach(fn => fn(direction));
}
