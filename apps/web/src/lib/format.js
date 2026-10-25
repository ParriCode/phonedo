// Formato de importes, fechas, direcciones e identificadores.
import { CONFIG } from '../config.js';

export const short = (s, a = 4, b = 4) => (s && s.length > a + b + 1 ? `${s.slice(0, a)}…${s.slice(-b)}` : s || '—');
export const txUrl = (hash) => `${CONFIG.explorer}/tx/${hash}`;
export const contractUrl = (id) => `${CONFIG.explorer}/contract/${id}`;
export const isAccount = (s) => /^G[A-Z2-7]{55}$/.test(s);

export function formatAmount(n, lang) {
  return n.toLocaleString(lang, { maximumFractionDigits: 2 });
}

export function timeAgo(iso, lang, t) {
  if (!iso) return t('time.unknown');
  const seconds = Math.round((new Date(iso) - Date.now()) / 1000);
  if (Math.abs(seconds) < 45) return t('time.now');
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: 'auto' });
  const units = [['day', 86400], ['hour', 3600], ['minute', 60]];
  for (const [unit, size] of units) {
    if (Math.abs(seconds) >= size) return rtf.format(Math.round(seconds / size), unit);
  }
  return rtf.format(seconds, 'second');
}

export function slug(text) {
  return text.toLowerCase().normalize('NFD').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'node';
}

export function portOf(url, fallback) {
  try { return Number(new URL(url).port) || fallback; } catch { return fallback; }
}

export function download(name, text) {
  const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
  const a = Object.assign(document.createElement('a'), { href: url, download: name });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
