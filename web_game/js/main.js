import { CFG, CARS, MELODIES, isCarUnlocked } from './cfg.js';
import { renderer, scene, camera, pinkLight, cyanLight, applyCarTheme, setBackground } from './scene.js';
import { state, resetState } from './state.js';
import { buildRoadPool, buildStarfield, tickRoad } from './road.js';
import { car, buildPlayer, loadCarModel, tickPlayer } from './player.js';
import { onLaneChange, onJump } from './input.js';
import { ensureAudio, resetBeat, toggleMute, getMuted, playMelodyNote, playCollisionSound, playLaserHitSound, playCoinSound, playWarpSound } from './audio.js';
import { spawnPatternBeat, spawnBolt, spawnHeart, spawnBird, spawnDrone, spawnCoin, tickBlocks, tickLasers, clearBlocks } from './blocks.js';
import { getCoins, addCoins, getItemCount, consumeItem, buildStoreGrid } from './store.js';
import { flash, updateHUD, showGameScreen, showGameOverScreen, showWinScreen, showStartScreen, buildCarGrid, setSongLabel, hideSongLabel, setMuteButtonState, showLevelBanner, showBoostBanner, showShieldBanner, showNewBest, showCountdown, showUnlockNotification } from './ui.js';
import { saveScore, renderLeaderboard, getPersonalBest } from './leaderboard.js';
import { buildParticles, tickParticles, setParticleColor, initSpeedLines, tickSpeedLines, triggerWarp } from './particles.js';

// ── Haptic ────────────────────────────────────────────────────
const vibrate = (ms) => navigator.vibrate?.(ms);

// ── Input ─────────────────────────────────────────────────────
function handleLaneChange(dir) {
  if (state.phase !== 'playing') return;
  const next = state.lane + dir;
  if (next < 0 || next > 2) {
    if (state.shielded) {
      state.shielded = false;
      flash('rgba(0,255,255,1)', 0.4);
      return;
    }
    state.lives--;
    state.combo      = 0;
    state.shakeUntil = state.elapsed + 0.35;
    state.shakeMag   = 0.25;
    playCollisionSound();
    vibrate(120);
    flash('rgba(255,0,40,1)', 0.45);
    updateHUD();
    if (state.lives <= 0) triggerGameOver();
    return;
  }
  state.lane    = next;
  state.targetX = CFG.LANES[next];
}

function handleJump() {
  if (state.phase !== 'playing') return;
  if (state.jumpsUsed < 2) {
    state.jumpVelocity = CFG.JUMP_FORCE;
    state.jumpsUsed++;
  }
}

onLaneChange(handleLaneChange);
onJump(handleJump);
// Touch swipe events — dispatched by inline script in index.html (cache-proof).
document.addEventListener('swipelane', e => handleLaneChange(e.detail));
document.addEventListener('swipejump', handleJump);

const MELODY_KEYS = Object.keys(MELODIES);

// Drone spawn interval per level (ms). null = no drones at that level.
const DRONE_INTERVALS = [null, null, 20000, 14000, 10000, 7000];

// ── Game flow ─────────────────────────────────────────────────
function startGame() {
  clearInterval(state.beatTimer);
  clearInterval(state.boltTimer);
  clearInterval(state.heartTimer);
  clearInterval(state.birdTimer);
  clearInterval(state.droneTimer);
  clearInterval(state.coinTimer);
  clearBlocks();
  resetState();

  // Consume single-use perks
  if (consumeItem('extra_life'))   { state.perkExtraLife = true; state.lives = CFG.LIVES + 1; }
  if (consumeItem('double_coins')) state.perkDoubleCoins = true;
  if (consumeItem('magnet'))       state.perkMagnet = true;

  // Head start: show button if player owns any
  const hsCount = getItemCount('head_start');
  if (hsCount > 0) {
    state.headStartReady = true;
    const hsBtn = document.getElementById('head-start-btn');
    const hsCnt = document.getElementById('head-start-count');
    hsCnt.textContent = `×${hsCount}`;
    hsBtn.classList.remove('hidden');
  }

  state.phase = 'countdown';
  applyCarTheme(CARS[state.selectedCarIdx].theme);
  setParticleColor(CARS[state.selectedCarIdx].theme.light1);
  resetBeat();
  car.position.x = CFG.LANES[1];
  loadCarModel(state.selectedCarIdx);
  ensureAudio();
  setMuteButtonState(getMuted());

  state.survivorPlaylist = [...MELODY_KEYS];
  for (let i = state.survivorPlaylist.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [state.survivorPlaylist[i], state.survivorPlaylist[j]] = [state.survivorPlaylist[j], state.survivorPlaylist[i]];
  }
  setSongLabel(MELODIES[state.survivorPlaylist[0]].label);

  showGameScreen();
  updateHUD();
  runCountdown();
}

function runCountdown() {
  let n = 3;
  showCountdown(n);
  const tick = setInterval(() => {
    n--;
    if (n > 0) {
      showCountdown(n);
    } else {
      showCountdown(0); // GO!
      clearInterval(tick);
      setTimeout(beginPlay, 800);
    }
  }, 1000);
}

function activateHeadStart() {
  if (!state.headStartReady) return;
  consumeItem('head_start');
  state.headStartReady = false;
  document.getElementById('head-start-btn').classList.add('hidden');

  // Warp visual + audio effect
  triggerWarp(1.5);
  playWarpSound();
  const baseFov = camera.fov;
  const warpFov = baseFov + 30;
  const warpMs  = 1500;
  const startT  = performance.now();
  function animFov() {
    const t = Math.min((performance.now() - startT) / warpMs, 1);
    // Ease: quick ramp up, slow settle back
    const curve = t < 0.3 ? t / 0.3 : 1 - ((t - 0.3) / 0.7);
    camera.fov = baseFov + (warpFov - baseFov) * curve;
    camera.updateProjectionMatrix();
    if (t < 1) requestAnimationFrame(animFov);
  }
  requestAnimationFrame(animFov);

  // Boost to level 2
  state.level = 2;
  state.lastLevelUp = state.elapsed;
  const lvlCfg = CFG.LEVELS[1];
  state.speed = lvlCfg.speed;
  applyCarTheme(lvlCfg.theme);
  restartBeatTimer(lvlCfg.beatMs);
  showLevelBanner(2);
  flash('rgba(255,215,0,1)', 0.4);
  updateHUD();
}

function hideHeadStartBtn() {
  state.headStartReady = false;
  document.getElementById('head-start-btn').classList.add('hidden');
}

function beginPlay() {
  state.phase = 'playing';
  restartBeatTimer(CFG.LEVELS[0].beatMs);

  // Auto-hide head start button after 5 seconds
  if (state.headStartReady) {
    setTimeout(() => { if (state.headStartReady) hideHeadStartBtn(); }, 5000);
  }

  clearInterval(state.boltTimer);
  state.boltTimer = setInterval(() => {
    if (state.phase !== 'playing') return;
    spawnBolt();
  }, CFG.BOLT_INTERVAL_MS);

  clearInterval(state.heartTimer);
  state.heartTimer = setInterval(() => {
    if (state.phase !== 'playing') return;
    spawnHeart();
  }, CFG.HEART_INTERVAL_MS);

  clearInterval(state.birdTimer);
  state.birdTimer = setInterval(() => {
    if (state.phase !== 'playing') return;
    spawnBird();
  }, CFG.BIRD_INTERVAL_MS);

  clearInterval(state.coinTimer);
  state.coinTimer = setInterval(() => {
    if (state.phase !== 'playing') return;
    spawnCoin();
  }, CFG.COIN_INTERVAL_MS);
}

function restartBeatTimer(ms) {
  clearInterval(state.beatTimer);
  state.beatTimer = setInterval(() => {
    if (state.phase !== 'playing') return;
    spawnPatternBeat();
  }, ms);
}

function restartDroneTimer() {
  clearInterval(state.droneTimer);
  const idx = Math.min(state.level - 1, DRONE_INTERVALS.length - 1);
  const ms  = DRONE_INTERVALS[idx];
  if (!ms) return; // no drones at this level
  state.droneTimer = setInterval(() => {
    if (state.phase !== 'playing') return;
    spawnDrone();
  }, ms);
}

function checkLevelUp() {
  if (state.elapsed - state.lastLevelUp < CFG.LEVEL_DURATION) return;
  state.lastLevelUp = state.elapsed;
  state.level++;
  const lvlCfg = CFG.LEVELS[Math.min(state.level - 1, CFG.LEVELS.length - 1)];
  state.speed = lvlCfg.speed;
  applyCarTheme(lvlCfg.theme);
  setParticleColor(lvlCfg.theme.light1);
  setBackground(CFG.BACKGROUNDS[Math.floor(Math.random() * CFG.BACKGROUNDS.length)]);
  restartBeatTimer(lvlCfg.beatMs);
  restartDroneTimer();
  showLevelBanner(state.level);
  updateHUD();
}

function triggerGameOver() {
  state.phase = 'gameover';
  clearInterval(state.beatTimer);
  clearInterval(state.boltTimer);
  clearInterval(state.heartTimer);
  clearInterval(state.birdTimer);
  clearInterval(state.droneTimer);
  clearInterval(state.coinTimer);
  hideHeadStartBtn();
  hideSongLabel();
  const prev = getPersonalBest();
  saveScore(state.score);
  const unlocked = checkNewUnlocks(prev);
  showGameOverScreen();
  if (state.score > prev) showNewBest('go');
  if (unlocked.length) showUnlockNotification(unlocked);
  renderLeaderboard(document.getElementById('go-leaderboard'));
}

function triggerWin() {
  state.phase = 'gameover';
  clearInterval(state.beatTimer);
  clearInterval(state.boltTimer);
  clearInterval(state.heartTimer);
  clearInterval(state.droneTimer);
  clearInterval(state.birdTimer);
  clearInterval(state.coinTimer);
  hideHeadStartBtn();
  const prev = getPersonalBest();
  saveScore(state.score);
  const unlocked = checkNewUnlocks(prev);
  showWinScreen(MELODY_KEYS.length);
  if (state.score > prev) showNewBest('win');
  if (unlocked.length) showUnlockNotification(unlocked);
  renderLeaderboard(document.getElementById('win-leaderboard'));
}

function checkNewUnlocks(prevBest) {
  const newBest = getPersonalBest();
  return CARS.filter(c => c.unlockScore > 0 && c.unlockScore > prevBest && c.unlockScore <= newBest);
}

// ── Collision processing ──────────────────────────────────────
// Lives here (not in blocks.js) to avoid a circular dependency:
// blocks.js → ui.js → state.js would be fine structurally, but
// blocks.js also needing to call triggerGameOver() would require
// importing from main.js, which imports blocks.js.
function processCollisions() {
  for (const block of state.blocks) {
    if (block.processed) continue;
    if (Math.abs(block.mesh.position.z - CFG.PLAYER_Z) > CFG.HIT_WINDOW) continue;

    block.processed  = true;
    const inLane     = block.lane === state.lane;

    if (block.type === 'heart') {
      if (inLane && !state.shielded) {
        state.shielded = true;
        flash('rgba(0,255,255,1)', 0.25);
        showShieldBanner();
        scene.remove(block.mesh);
      }
    } else if (block.type === 'bolt') {
      if (inLane) {
        state.boostUntil = state.elapsed + CFG.BOOST_DURATION;
        state.speed      = CFG.LEVELS[Math.min(state.level - 1, CFG.LEVELS.length - 1)].speed * CFG.BOOST_SPEED_MULT;
        flash('rgba(255,215,0,1)', 0.35);
        showBoostBanner();
        scene.remove(block.mesh);
      }
    } else if (block.type === 'coin') {
      const airborne   = car.position.y > CFG.COIN_Y + 1.0;
      const canCollect = (inLane && !airborne) || state.perkMagnet;
      if (canCollect) {
        let value = CFG.COIN_VALUE;
        if (state.perkDoubleCoins) value *= 2;
        state.coinsThisRun += value;
        addCoins(value);
        playCoinSound();
        flash('rgba(255,215,0,1)', 0.2);
        scene.remove(block.mesh);
      }
    } else if (block.type === 'bird' || block.type === 'drone') {
      const inFlight = inLane && car.position.y >= CFG.BIRD_HIT_MIN_Y && car.position.y <= CFG.BIRD_HIT_MAX_Y;
      if (inFlight) {
        if (state.shielded) {
          state.shielded = false;
          flash('rgba(0,255,255,1)', 0.4);
          scene.remove(block.mesh);
          updateHUD();
          continue;
        }
        state.lives--;
        state.combo = 0;
        block.knockbackVZ   = 90;
        block.knockbackRotY = (Math.random() > 0.5 ? 1 : -1) * 8;
        state.shakeUntil    = state.elapsed + 0.35;
        state.shakeMag      = 0.25;
        playCollisionSound();
        vibrate(120);
        flash('rgba(255,0,40,1)', 0.45);
        updateHUD();
        if (state.lives <= 0) { triggerGameOver(); return; }
      }
    } else if (block.type === 'green') {
      if (inLane) {
        state.combo++;
        state.maxCombo   = Math.max(state.maxCombo, state.combo);
        const multIdx    = Math.min(state.combo - 1, CFG.COMBO_MULTS.length - 1);
        state.score     += CFG.POINTS_BASE * CFG.COMBO_MULTS[multIdx];
        state.collected++;
        const melody = MELODIES[state.survivorPlaylist[state.survivorSongIdx]].notes;
        playMelodyNote(melody[state.melodyIdx]);
        state.melodyIdx++;
        if (state.melodyIdx >= melody.length) {
          state.melodyIdx = 0;
          state.survivorSongIdx++;
          if (state.survivorSongIdx >= MELODY_KEYS.length) {
            triggerWin(); return;
          }
          setSongLabel(MELODIES[state.survivorPlaylist[state.survivorSongIdx]].label);
        }
        vibrate(20);
        flash('rgba(0,255,136,1)', 0.14);
        scene.remove(block.mesh);
      } else {
        state.combo = 0;
        flash('rgba(255,220,0,1)', 0.10);
      }
    } else {
      const airborne = car.position.y > CFG.GROUND_Y + 0.3;
      if (inLane && !airborne) {
        if (state.shielded) {
          state.shielded = false;
          flash('rgba(0,255,255,1)', 0.4);
          scene.remove(block.mesh);
          updateHUD();
          continue;
        }
        state.lives--;
        state.combo = 0;
        block.knockbackVZ   = 90;
        block.knockbackRotY = (Math.random() > 0.5 ? 1 : -1) * 8;
        state.shakeUntil    = state.elapsed + 0.35;
        state.shakeMag      = 0.25;
        playCollisionSound();
        vibrate(120);
        flash('rgba(255,0,40,1)', 0.45);
        updateHUD();
        if (state.lives <= 0) { triggerGameOver(); return; }
      } else if (!inLane) {
        state.dodged++;
      }
    }
    updateHUD();
  }
}

// ── Laser collision ──────────────────────────────────────────
function processLaserCollisions() {
  for (let i = state.lasers.length - 1; i >= 0; i--) {
    const l = state.lasers[i];
    const dx = l.mesh.position.x - car.position.x;
    const dy = l.mesh.position.y - car.position.y;
    const dz = l.mesh.position.z - car.position.z;
    if (dx * dx + dy * dy + dz * dz > 2.25) continue; // 1.5 unit radius

    // Hit! Remove laser
    scene.remove(l.mesh);
    state.lasers.splice(i, 1);

    if (state.shielded) {
      state.shielded = false;
      flash('rgba(0,255,255,1)', 0.4);
      updateHUD();
      continue;
    }

    state.lives--;
    state.combo = 0;
    state.shakeUntil = state.elapsed + 0.3;
    state.shakeMag   = 0.2;
    playLaserHitSound();
    vibrate(100);
    flash('rgba(255,0,0,1)', 0.5);
    updateHUD();
    if (state.lives <= 0) { triggerGameOver(); return; }
  }
}

// ── Per-frame update ──────────────────────────────────────────
function update(dt) {
  if (state.phase !== 'playing') return;

  state.elapsed += dt;
  checkLevelUp();

  // Expire speed boost — restore current level's base speed
  if (state.boostUntil > 0 && state.elapsed >= state.boostUntil) {
    state.boostUntil = 0;
    state.speed = CFG.LEVELS[Math.min(state.level - 1, CFG.LEVELS.length - 1)].speed;
  }

  tickPlayer(dt, state.targetX, state);
  tickRoad(dt, state.speed);
  tickBlocks(dt);
  tickLasers(dt);
  tickParticles(dt);
  tickSpeedLines(dt);
  processCollisions();
  processLaserCollisions();

  const currentBeatMs = CFG.LEVELS[Math.min(state.level - 1, CFG.LEVELS.length - 1)].beatMs;
  const beatPhase     = state.elapsed * (1000 / currentBeatMs) * Math.PI;
  pinkLight.intensity = 1.6 + Math.sin(beatPhase) * 1.0;
  cyanLight.intensity = 1.2 + Math.cos(beatPhase) * 0.6;
}

// ── Animation loop ────────────────────────────────────────────
let lastT = 0;
function animate(t = 0) {
  requestAnimationFrame(animate);
  const dt = Math.min((t - lastT) / 1000, 0.05);
  lastT = t;
  update(dt);
  renderer.render(scene, camera);
}

// ── Boot ──────────────────────────────────────────────────────
document.getElementById('btn-start').addEventListener('click', () => {
  state.survivorMode = true;
  startGame();
});
function updateWalletDisplay() {
  document.getElementById('wallet-display').textContent = `${getCoins()} coins`;
}

function returnToStart() {
  const best = getPersonalBest();
  if (!isCarUnlocked(state.selectedCarIdx, best)) {
    state.selectedCarIdx = 0;
  }
  buildCarGrid((idx) => { state.selectedCarIdx = idx; });
  updateWalletDisplay();
  showStartScreen();
}
document.getElementById('btn-restart').addEventListener('click', returnToStart);
document.getElementById('btn-win-restart').addEventListener('click', returnToStart);
document.getElementById('btn-mute').addEventListener('click', () => {
  setMuteButtonState(toggleMute());
});

const lbScreen   = document.getElementById('screen-leaderboard');
const storeScr   = document.getElementById('screen-store');
const startScr   = document.getElementById('screen-start');
document.getElementById('btn-leaderboard').addEventListener('click', () => {
  renderLeaderboard(document.getElementById('lb-start-panel'));
  startScr.classList.add('hidden');
  lbScreen.classList.remove('hidden');
});
document.getElementById('btn-lb-close').addEventListener('click', () => {
  lbScreen.classList.add('hidden');
  startScr.classList.remove('hidden');
});

document.getElementById('head-start-btn').addEventListener('click', activateHeadStart);

document.getElementById('btn-store').addEventListener('click', () => {
  buildStoreGrid(document.getElementById('store-grid'), document.getElementById('store-wallet'));
  startScr.classList.add('hidden');
  storeScr.classList.remove('hidden');
});
document.getElementById('btn-store-close').addEventListener('click', () => {
  storeScr.classList.add('hidden');
  startScr.classList.remove('hidden');
  updateWalletDisplay();
});

buildRoadPool();
buildStarfield();
buildPlayer();
buildParticles();
initSpeedLines();
buildCarGrid((idx) => { state.selectedCarIdx = idx; });
updateWalletDisplay();
animate();
