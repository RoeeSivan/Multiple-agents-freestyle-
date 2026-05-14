const LS_KEY      = 'neon_highway_scores';
const MAX_ENTRIES = 10;

export function saveScore(score) {
  const entries = getScores();
  entries.push(score);
  entries.sort((a, b) => b - a);
  localStorage.setItem(LS_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
}

export function getPersonalBest() {
  const s = getScores();
  return s.length ? s[0] : 0;
}

export function getScores() {
  try   { return JSON.parse(localStorage.getItem(LS_KEY)) ?? []; }
  catch { return []; }
}

export function renderLeaderboard(el) {
  const scores = getScores();
  if (!scores.length) {
    el.innerHTML = '<div class="lb-empty">No scores yet — be the first!</div>';
    return;
  }
  el.innerHTML = scores.map((s, i) => {
    const rankClass = i === 0 ? 'lb-rank--gold'
                    : i === 1 ? 'lb-rank--silver'
                    : i === 2 ? 'lb-rank--bronze' : '';
    return `<div class="lb-row">
      <span class="lb-rank ${rankClass}">#${i + 1}</span>
      <span class="lb-score">${s.toLocaleString()}</span>
    </div>`;
  }).join('');
}
