/* Eatery offers posted by the restaurant (checked by the team before they show) and the
 * "Post a pujo offer" form. Backend: supabase/migrations/*_offers_menus.sql. */
import { G, idx, t, community, esc, loc } from './state.js';
import { openSheet, toast, rerender, $ } from './ui.js';
import { track } from './analytics.js';
import { foodSheet } from './sheets.js';

let OFFERS = {};
const todayIST = () => new Date(Date.now() + 5.5 * 3600e3).toISOString().slice(0, 10);
const addDays = (d, n) => new Date(Date.parse(d + 'T00:00:00Z') + n * 864e5).toISOString().slice(0, 10);
const dateText = (d) => new Date(d + 'T00:00').toLocaleDateString(loc(), { day: 'numeric', month: 'short' });

export async function loadOffers() {
  OFFERS = await community.offers();
  if (Object.keys(OFFERS).length) rerender();
}
export const offersOf = (id) => OFFERS[id] || [];

/** A small "Offer" tag for food tiles. */
export const offerChip = (id) => (offersOf(id).length ? `<span class="offer-chip">🏷️ ${t('of.chip')}</span>` : '');

/** The offers on an eatery page. */
export function offersHtml(id) {
  const list = offersOf(id);
  if (!list.length) return '';
  return `<div class="offers">${list.map((o) => `<div class="offer-card"><span class="oc-tag" aria-hidden="true">🏷️</span>
      <div><b>${esc(o.title)}</b>${o.details ? `<p>${esc(o.details)}</p>` : ''}
      <small>${o.valid_from > todayIST() ? t('of.from', { d: dateText(o.valid_from), e: dateText(o.valid_to) }) : t('of.till', { d: dateText(o.valid_to) })} · ${t('of.byPlace')}</small></div></div>`).join('')}</div>`;
}

const digits10 = (v) => { let d = String(v || '').replace(/\D/g, ''); if (d.length > 10 && /^(91|0)/.test(d)) d = d.replace(/^(91|0)/, ''); return d.slice(0, 10); };

/** "Post a pujo offer": for the owner or manager. The team calls back before it goes live. */
export function offerSheet(id) {
  if (!community.enabled) return toast(t('sy.off'));
  const f = idx.food[id], today = todayIST();
  const dashami = G.data.meta.days.find((d) => d.id === 'dashami')?.date;
  const to = dashami && dashami >= today ? dashami : addDays(today, 7);
  openSheet(`<h2 class="title">${t('of.postTitle')}</h2>
    <p class="fine" style="margin:4px 0 12px"><b>${esc(f.name)}</b> · ${t('of.postSub')}</p>
    <form id="offerForm" class="form" style="padding:0">
      <label>${t('of.what')}<input id="ofTitle" required minlength="3" maxlength="80" placeholder="${t('of.whatPh')}"></label>
      <label>${t('of.details')}<textarea id="ofDetails" maxlength="240" rows="2" placeholder="${t('of.detailsPh')}"></textarea></label>
      <div class="grid2"><label>${t('of.validFrom')}<input id="ofFrom" type="date" required min="${today}" max="${addDays(today, 60)}" value="${today}"></label>
        <label>${t('of.validTo')}<input id="ofTo" type="date" required min="${today}" max="${addDays(today, 60)}" value="${to}"></label></div>
      <label>${t('of.name')}<input id="ofName" required minlength="2" maxlength="60" autocomplete="name"></label>
      <label>${t('of.phone')}<span class="phone-in"><span class="cc">+91</span><input id="ofPhone" type="tel" inputmode="numeric" required pattern="[6-9][0-9]{9}" autocomplete="tel-national" placeholder="9830012345"></span></label>
      <label class="toggle"><input type="checkbox" id="ofOwner" required> <span>${t('of.owner')}</span></label>
      <button class="btn primary block" type="submit">${t('of.send')}</button>
      <p class="fine">${t('of.how')}</p>
    </form>`,
  (el) => {
    const ph = $('#ofPhone', el);
    ph.oninput = () => { const v = digits10(ph.value); if (v !== ph.value) ph.value = v; };
    $('#offerForm', el).onsubmit = async (e) => {
      e.preventDefault();
      const o = { placeId: id, title: $('#ofTitle', el).value.trim(), details: $('#ofDetails', el).value.trim(),
        from: $('#ofFrom', el).value, to: $('#ofTo', el).value, name: $('#ofName', el).value.trim(), phone: digits10(ph.value) };
      if (!/^[6-9]\d{9}$/.test(o.phone)) { ph.focus(); return toast(t('pr.badPhone')); }
      if (o.to < o.from) return toast(t('of.err.bad_dates'));
      const b = e.target.querySelector('button[type=submit]'); b.disabled = true;
      try {
        const r = await community.submitOffer(o);
        if (r.status === 'pending') { track('offer', { place: id, kind: 'food' }); toast(t('of.sent'), 5000); return foodSheet(id); }
        toast(t(['bad_phone', 'bad_title', 'bad_name', 'bad_dates', 'rate_limited'].includes(r.status) ? 'of.err.' + r.status : 'of.err.other'));
      } catch { toast(t('sy.failed')); }
      b.disabled = false;
    };
  });
}
