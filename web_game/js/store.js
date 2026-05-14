import { STORE_ITEMS } from './cfg.js';

const LS_KEY = 'neon_highway_store';

// Data shape: { coins: number, items: { [id]: quantity } }
function getStoreData() {
  try {
    const raw = JSON.parse(localStorage.getItem(LS_KEY)) ?? {};
    return { coins: raw.coins || 0, items: raw.items || {} };
  } catch { return { coins: 0, items: {} }; }
}

function saveStoreData(data) {
  localStorage.setItem(LS_KEY, JSON.stringify(data));
}

export function getCoins() {
  return getStoreData().coins;
}

export function addCoins(amount) {
  const data = getStoreData();
  data.coins += amount;
  saveStoreData(data);
}

export function purchaseItem(itemId) {
  const item = STORE_ITEMS.find(i => i.id === itemId);
  if (!item) return false;
  const data = getStoreData();
  if (data.coins < item.price) return false;
  data.coins -= item.price;
  data.items[itemId] = (data.items[itemId] || 0) + 1;
  saveStoreData(data);
  return true;
}

export function getItemCount(itemId) {
  return getStoreData().items[itemId] || 0;
}

export function consumeItem(itemId) {
  const data = getStoreData();
  if ((data.items[itemId] || 0) <= 0) return false;
  data.items[itemId]--;
  saveStoreData(data);
  return true;
}

const CONSUMABLE_ONE_TIME = ['extra_life', 'double_coins', 'magnet'];

export function buildStoreGrid(gridEl, walletEl) {
  const data = getStoreData();
  walletEl.textContent = `${data.coins} coins`;
  gridEl.innerHTML = '';

  STORE_ITEMS.forEach(item => {
    const qty = data.items[item.id] || 0;
    const isOneTime = CONSUMABLE_ONE_TIME.includes(item.id);
    const isSoldOut = isOneTime && qty > 0;
    const card = document.createElement('div');
    card.className = 'store-item' + (isSoldOut ? ' store-item--soldout' : '');

    card.innerHTML =
      `<span class="store-item-name">${item.label}</span>` +
      `<span class="store-item-desc">${item.description}</span>` +
      (qty > 0 ? `<span class="store-item-qty">owned: ${qty}</span>` : '') +
      (isSoldOut ? `<span class="store-item-soldout">ACTIVE NEXT RUN</span>` : 
       `<span class="store-item-price">${item.price} coins</span>`);

    if (!isSoldOut) {
      card.addEventListener('click', () => {
        if (purchaseItem(item.id)) {
          buildStoreGrid(gridEl, walletEl);
        } else {
          card.style.animation = 'locked-shake 0.4s';
          setTimeout(() => card.style.animation = '', 400);
        }
      });
    }

    gridEl.appendChild(card);
  });
}
