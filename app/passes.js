/* Home card: Kolkata's two Durga Puja VIP passes, compared in content/knowledge/durga-puja/pujo-pass.md (facts as of
 * 10 October 2026). Editorial, not paid: neither pass pays us, and the card says so. Hidden after Navami (20 Oct), the
 * last day either pass is valid. */
import { passPhase } from './core.js';
import { S, t, esc, bnDigits } from './state.js';

const WHEN = { lastCollect: '2026-10-14', until: '2026-10-20' };
const PASSES = [
  { name: 'Pujor Passport', name_bn: 'পুজোর পাসপোর্ট', by: 'Forum for Durgotsab', price: '₹999 + fee', n: 52, seller: 'BookMyShow', get: 'collect' },
  { name: 'Porikroma Map Invitee Card', name_bn: 'পরিক্রমা ম্যাপ ইনভাইটি কার্ড', by: 'Porikroma Map', price: '₹950', n: 54, seller: 'District (Zomato)', get: 'deliver' },
];

export function passCardHtml(now = new Date()) {
  const phase = passPhase(WHEN, now);
  if (!phase) return '';
  const rows = PASSES.map((x) => `<li><b>${esc(S.prefs.lang === 'bn' ? x.name_bn : x.name)}</b>
      <span class="pc-t">${esc(x.price)} · ${t('pass.n', { n: bnDigits(x.n) })} · ${esc(x.seller)}</span>
      <small>${t('pass.' + x.get)}</small></li>`).join('');
  return `<section class="section pass-card" aria-label="${t('pass.title')}"><div class="pc-box">
    <h2>🎟️ ${t('pass.title')}</h2><p class="sub">${t('pass.sub')}</p>
    <ul class="pc-rows">${rows}</ul>
    <p class="pc-pick">${t(phase === 'late' ? 'pass.pickLate' : 'pass.pick')}</p>
    <a class="link-btn" href="durga-puja/pujo-pass/">${t('pass.cta')}</a>
    <p class="fine">${t('pass.note')}</p></div></section>`;
}
