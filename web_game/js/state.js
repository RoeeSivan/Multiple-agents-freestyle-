import { CFG } from './cfg.js';

// Single shared mutable state object. Imported by reference — mutations in one
// module are immediately visible to all others.
export const state = {
  phase:      'start',          // 'start' | 'playing' | 'gameover'
  speed:      CFG.LEVELS[0].speed,
  score:      0,
  combo:      0,
  lives:      CFG.LIVES,
  lane:       1,                // 0 = left | 1 = centre | 2 = right
  targetX:    CFG.LANES[1],
  elapsed:     0,               // seconds since game start
  level:       1,               // current difficulty level (1-based)
  lastLevelUp: 0,               // elapsed value at the last level-up
  blocks:     [],               // { mesh, lane, type, processed, knockbackVZ?, knockbackRotY? }[]
  lasers:     [],               // { mesh, lane }[] — active laser projectiles
  patternIdx: 0,
  beatTimer:  null,
  maxCombo:      0,
  collected:     0,
  dodged:        0,
  jumpVelocity:     0,
  melodyIdx:        0,
  shakeUntil:      0,          // state.elapsed value when camera shake ends
  shakeMag:        0,          // peak shake offset in world units
  boostUntil:      0,          // state.elapsed value when speed boost ends
  boltTimer:       null,
  shielded:        false,
  jumpsUsed:       0,
  heartTimer:      null,
  birdTimer:       null,
  droneTimer:      null,
  survivorPlaylist: [],        // shuffled melody keys for the current survivor run
  survivorMode:     false,
  survivorSongIdx:  0,
  selectedCarIdx:   0,          // persists across restarts — intentionally omitted from resetState()
  coinsThisRun:     0,
  coinTimer:        null,
  // Per-round consumable perks (consumed from store on game start)
  perkDoubleCoins:  false,
  perkMagnet:       false,
  perkExtraLife:    false,
  headStartReady:   false,    // true if player has head starts and hasn't used/dismissed yet
};

export function resetState() {
  state.phase      = 'playing';
  state.speed      = CFG.LEVELS[0].speed;
  state.score      = 0;
  state.combo      = 0;
  state.lives      = CFG.LIVES;
  state.lane       = 1;
  state.targetX    = CFG.LANES[1];
  state.elapsed    = 0;
  state.level      = 1;
  state.lastLevelUp = 0;
  state.blocks     = [];
  state.lasers     = [];
  state.patternIdx = 0;
  state.maxCombo      = 0;
  state.collected     = 0;
  state.dodged        = 0;
  state.jumpVelocity     = 0;
  state.melodyIdx        = 0;
  state.survivorSongIdx  = 0;
  state.survivorPlaylist = [];
  state.shakeUntil       = 0;
  state.shakeMag         = 0;
  state.boostUntil       = 0;
  state.shielded         = false;
  state.jumpsUsed        = 0;
  state.coinsThisRun     = 0;
  state.perkDoubleCoins  = false;
  state.perkMagnet       = false;
  state.perkExtraLife    = false;
  state.headStartReady   = false;
}
