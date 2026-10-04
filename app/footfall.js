/* Expected footfall: estimates, always labelled "est." in the UI and never mixed into real check-in counts.
 * Pandals: peak-day visitors by popularity tier (in line with reported crowds at big Kolkata pujas, where the
 * top theme pandals draw several lakh a day around Ashtami), scaled by the puja-day crowd factor, with a
 * steady per-pandal spread so neighbours don't show identical numbers. Eateries: diners a day by type and price. */
import { S, idx, bnDigits } from './state.js';

const PEAK = { 5: 350000, 4: 120000, 3: 40000, 2: 15000, 1: 6000 };
const DINERS = { sweets: 2400, street: 1600, cabin: 900, restaurant: 1300, drinks: 1100 };
// Stable 0..1 from an id, so a place's estimate doesn't jump between visits.
const spread = (id) => { let h = 2166136261; for (const c of id) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return (h >>> 0) / 4294967296; };
const round = (n, to) => Math.max(to, Math.round(n / to) * to);
const factor = (day) => idx.day[day || S.day]?.factor ?? 1;

export const estVisitors = (p, day) => round((PEAK[p.popularity] || 6000) * (0.65 + 0.7 * spread(p.id)) * factor(day), 1000);
export const estDiners = (f, day) => round((DINERS[f.type] || 1000) * (f.price === 1 ? 1.25 : f.price === 3 ? 0.65 : 1) * (0.6 + 0.8 * spread(f.id)) * Math.max(0.5, factor(day)), 50);

/** 350000 -> "3.5L", 42000 -> "42k" (Indian short form; Bengali digits in Bengali). */
export function short(n) {
  const s = n >= 100000 ? `${(n / 100000).toFixed(n >= 1000000 ? 0 : 1).replace(/\.0$/, '')}L` : n >= 1000 ? `${Math.round(n / 1000)}k` : String(n);
  return bnDigits(s);
}
