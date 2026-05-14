import { CFG, CARS, isCarUnlocked } from './cfg.js';
import { state } from './state.js';
import { getPersonalBest } from './leaderboard.js';

// Cache DOM references once at module load — avoids repeated getElementById calls.
const flashEl        = document.getElementById('flash');
const countdownEl    = document.getElementById('countdown-banner');
const hudEl       = document.getElementById('hud');
const scoreEl     = document.getElementById('hud-score');
const comboEl     = document.getElementById('hud-combo');
const livesEl     = document.getElementById('hud-lives');
const levelEl     = document.getElementById('hud-level');
const levelBanner = document.getElementById('level-banner');
const goScoreEl   = document.getElementById('go-score');
const goStatsEl   = document.getElementById('go-stats');
const goNewBest   = document.getElementById('go-newbest');
const winNewBest  = document.getElementById('win-newbest');
const startScr    = document.getElementById('screen-start');
const gameoverScr = document.getElementById('screen-gameover');
const carGridEl   = document.getElementById('car-grid');
const winScr      = document.getElementById('screen-win');
const winScoreEl  = document.getElementById('win-score');
const winSubEl    = document.getElementById('win-subtitle');
const winStatsEl  = document.getElementById('win-stats');
const songLabelEl = document.getElementById('song-label');
const songLabelTx = document.getElementById('song-label-text');
const muteBtnEl   = document.getElementById('btn-mute');
const coinsEl     = document.getElementById('hud-coins');

export function flash(color, alpha = 0.25) {
  flashEl.style.background = color;
  flashEl.style.opacity    = alpha;
  setTimeout(() => { flashEl.style.opacity = 0; }, 75);
}

export function updateHUD() {
  const multIdx   = Math.min(Math.max(state.combo - 1, 0), CFG.COMBO_MULTS.length - 1);
  scoreEl.textContent = state.score.toLocaleString();
  comboEl.textContent = `x${CFG.COMBO_MULTS[multIdx]}`;
  livesEl.textContent = '♥ '.repeat(state.lives).trim() +
                        (' ♡'.repeat(Math.max(0, CFG.LIVES - state.lives)));
  levelEl.textContent = `${state.level}`;
  coinsEl.textContent = state.coinsThisRun;
}

export function showLevelBanner(level) {
  levelBanner.textContent = `LEVEL ${level}`;
  levelBanner.style.color = '#ffffff';
  levelBanner.classList.remove('level-banner--show');
  void levelBanner.offsetWidth;
  levelBanner.classList.add('level-banner--show');
}

export function showCountdown(n) {
  const isGo = n === 0;
  countdownEl.textContent = isGo ? 'GO!' : n;
  countdownEl.style.color = isGo ? '#00ff88' : '#ffffff';
  countdownEl.style.textShadow = isGo
    ? '0 0 20px #00ff88, 0 0 40px #00ff88'
    : '0 0 20px #fff, 0 0 40px #ff00ff';
  countdownEl.classList.remove('countdown--show');
  void countdownEl.offsetWidth;
  countdownEl.classList.add('countdown--show');
}

export function showShieldBanner() {
  levelBanner.textContent = 'SHIELD!';
  levelBanner.style.color = '#00ffff';
  levelBanner.classList.remove('level-banner--show');
  void levelBanner.offsetWidth;
  levelBanner.classList.add('level-banner--show');
}

export function showBoostBanner() {
  levelBanner.textContent = 'BOOST!';
  levelBanner.style.color = '#ffd700';
  levelBanner.classList.remove('level-banner--show');
  void levelBanner.offsetWidth;
  levelBanner.classList.add('level-banner--show');
}

export function showStartScreen() {
  startScr.classList.remove('hidden');
  gameoverScr.classList.add('hidden');
  winScr.classList.add('hidden');
  hudEl.classList.add('hidden');
  songLabelEl.classList.add('hidden');
}

export function showGameScreen() {
  startScr.classList.add('hidden');
  gameoverScr.classList.add('hidden');
  winScr.classList.add('hidden');
  hudEl.classList.remove('hidden');
}

export function showWinScreen(totalSongs) {
  const multIdx = Math.min(state.maxCombo, CFG.COMBO_MULTS.length - 1);
  winScoreEl.textContent = state.score.toLocaleString();
  winSubEl.textContent   = `YOU BEAT ALL ${totalSongs} SONGS!`;
  winStatsEl.textContent =
    `MAX COMBO x${CFG.COMBO_MULTS[multIdx]}  ·  COLLECTED ${state.collected}  ·  DODGED ${state.dodged}  ·  COINS +${state.coinsThisRun}`;
  winNewBest.classList.add('hidden');
  winScr.classList.remove('hidden');
  hudEl.classList.add('hidden');
  songLabelEl.classList.add('hidden');
}

export function setSongLabel(name) {
  songLabelTx.textContent = name;
  songLabelEl.classList.remove('hidden');
}

export function hideSongLabel() {
  songLabelEl.classList.add('hidden');
}

export function showGameOverScreen() {
  const multIdx   = Math.min(state.maxCombo, CFG.COMBO_MULTS.length - 1);
  goScoreEl.textContent = state.score.toLocaleString();
  goStatsEl.textContent =
    `MAX COMBO x${CFG.COMBO_MULTS[multIdx]}  ·  COLLECTED ${state.collected}  ·  DODGED ${state.dodged}  ·  COINS +${state.coinsThisRun}`;
  goNewBest.classList.add('hidden');
  gameoverScr.classList.remove('hidden');
  hudEl.classList.add('hidden');
}

export function showNewBest(prefix) {
  (prefix === 'go' ? goNewBest : winNewBest).classList.remove('hidden');
}

// Builds the car selection grid and wires click handlers.
// onSelect(idx) is called whenever the user picks a car.
export function buildCarGrid(onSelect) {
  carGridEl.innerHTML = '';
  const best = getPersonalBest();

  CARS.forEach((carDef, idx) => {
    const unlocked = isCarUnlocked(idx, best);
    const card = document.createElement('div');

    if (unlocked) {
      card.className = 'car-card' + (idx === state.selectedCarIdx ? ' car-card--selected' : '');
      card.textContent = carDef.label;
      card.addEventListener('click', () => {
        carGridEl.querySelectorAll('.car-card').forEach(c => c.classList.remove('car-card--selected'));
        card.classList.add('car-card--selected');
        onSelect(idx);
      });
    } else {
      card.className = 'car-card car-card--locked';
      card.innerHTML =
        `<span class="car-lock-icon">&#x1F512;</span>` +
        `<span class="car-lock-label">${carDef.label}</span>` +
        `<span class="car-lock-score">${carDef.unlockScore.toLocaleString()} pts</span>`;
      card.addEventListener('click', () => {
        card.classList.add('car-card--locked-shake');
        setTimeout(() => card.classList.remove('car-card--locked-shake'), 400);
      });
    }

    carGridEl.appendChild(card);
  });
}


// Syncs the mute button label/style to the current muted state.
export function setMuteButtonState(isMuted) {
  muteBtnEl.textContent = isMuted ? 'UNMUTE' : 'MUTE';
  muteBtnEl.classList.toggle('btn-mute--active', isMuted);
}

export function showUnlockNotification(cars) {
  const names = cars.map(c => c.label).join(', ');
  const el = document.createElement('div');
  el.className = 'unlock-notification';
  el.innerHTML =
    `<div class="unlock-icon">&#x1F513;</div>` +
    `<div class="unlock-text">CAR UNLOCKED</div>` +
    `<div class="unlock-name">${names}</div>`;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}
