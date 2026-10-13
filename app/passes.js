/* Home link: Kolkata's two Durga Puja VIP passes, compared in content/knowledge/durga-puja/pujo-pass.md (facts as of
 * 10 October 2026). Editorial, not paid. A single quiet row below the core modules, never above them; hidden after
 * Navami (20 Oct), the last day either pass is valid. */
import { passPhase } from './core.js';
import { t, esc } from './state.js';

const WHEN = { lastCollect: '2026-10-14', until: '2026-10-20' };
const PASSES = [
  { name: 'Pujor Passport', name_bn: 'পুজোর পাসপোর্ট', by: 'Forum for Durgotsab', price: '₹999 + fee', n: 52, seller: 'BookMyShow', get: 'collect' },
  { name: 'Porikroma Map Invitee Card', name_bn: 'পরিক্রমা ম্যাপ ইনভাইটি কার্ড', by: 'Porikroma Map', price: '₹950', n: 54, seller: 'District (Zomato)', get: 'deliver' },
];

export function passCardHtml(now = new Date()) {
  const phase = passPhase(WHEN, now);
  if (!phase) return '';
  const from = PASSES.map((x) => x.price).join(' / ');
  return `<section class="section pass-link-wrap" aria-label="${t('pass.title')}">
    <a class="pass-link" href="durga-puja/pujo-pass/"><span class="pl-ic" aria-hidden="true">🎟️</span>
      <span class="pl-tx"><b>${t('pass.title')}</b><small>${esc(from)} · ${t('pass.cta')}</small></span>
      <span class="pl-go" aria-hidden="true">›</span></a></section>`;
}
