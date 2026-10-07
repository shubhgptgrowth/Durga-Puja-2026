/* Eatery offers posted by the restaurant (checked by the team before they show) and the
 * "Post a pujo offer" form. Backend: supabase/migrations/*_offers_menus.sql and *_featured_offers.sql.
 * A featured (paid) offer is always labelled "Sponsored"; it moves its eatery up in food lists and nothing else. */
import { G, idx, t, community, esc, loc } from './state.js';
import { CONFIG } from './config.js';
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
/** True while this eatery has a paid, featured offer running. */
export const isFeatured = (id) => offersOf(id).some((o) => o.featured);
/** Featured eateries first, everything else in its existing order (a stable sort, so distance order holds). */
export const featuredFirst = (list, idOf = (x) => x.id) => list.map((x, i) => [x, i])
  .sort((a, b) => (isFeatured(idOf(b[0])) - isFeatured(idOf(a[0]))) || a[1] - b[1]).map(([x]) => x);

/** A small "Offer" tag for food tiles; featured ones say "Sponsored". */
export const offerChip = (id) => (!offersOf(id).length ? ''
  : isFeatured(id) ? `<span class="offer-chip featured">★ ${t('of.sponsoredChip')}</span>` : `<span class="offer-chip">🏷️ ${t('of.chip')}</span>`);
/** The "Sponsored" label for featured eateries in other lists. */
export const sponsoredTag = (id) => (isFeatured(id) ? `<span class="sponsored">${t('of.sponsored')}</span>` : '');

/** The offers on an eatery page. */
export function offersHtml(id) {
  const list = offersOf(id);
  if (!list.length) return '';
  return `<div class="offers">${list.map((o) => `<div class="offer-card ${o.featured ? 'featured' : ''}"><span class="oc-tag" aria-hidden="true">${o.featured ? '★' : '🏷️'}</span>
      <div>${o.featured ? `<span class="sponsored">${t('of.sponsored')}</span>` : ''}<b>${esc(o.title)}</b>${o.details ? `<p>${esc(o.details)}</p>` : ''}
      <small>${o.valid_from > todayIST() ? t('of.from', { d: dateText(o.valid_from), e: dateText(o.valid_to) }) : t('of.till', { d: dateText(o.valid_to) })} · ${t('of.byPlace')}</small></div></div>`).join('')}</div>`;
}

const F = CONFIG.featured || {};
const PRICE = Number(F.priceInr) || 0;
const rupees = (n) => '₹' + Number(n).toLocaleString('en-IN');
/** A UPI deep link (any UPI app). The note carries the offer's short id so the team can match the payment. */
export const upiLink = (offerId) => `upi://pay?${new URLSearchParams({ pa: F.upiId, pn: F.payeeName || 'Pujo Parikrama', am: String(PRICE), cu: 'INR',
  tn: `Featured offer ${String(offerId || '').slice(0, 8)}` })}`;

/** After a "feature this" offer is sent: what happens next, and a UPI button when one is set up. */
function paySheet(id, offerId) {
  const f = idx.food[id];
  openSheet(`<h2 class="title">${t('of.payTitle')}</h2>
    <p class="fine" style="margin:4px 0 12px"><b>${esc(f.name)}</b></p>
    <p>${t('of.paySub', { p: rupees(PRICE) })}</p>
    ${F.upiId ? `<a class="btn primary block" id="ofPay" href="${esc(upiLink(offerId))}">${t('of.payBtn', { p: rupees(PRICE) })}</a>
      <p class="fine">${t('of.payNote', { ref: esc(String(offerId || '').slice(0, 8)) })}</p>` : `<p class="fine">${t('of.payLater')}</p>`}
    <button class="btn block" id="ofDone" style="margin-top:8px">${t('of.payDone')}</button>`,
  (el) => {
    $('#ofPay', el)?.addEventListener('click', () => track('offer', { place: id, kind: 'food', d: 'upi' }));
    $('#ofDone', el).onclick = () => foodSheet(id);
  });
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
      ${PRICE ? `<label class="toggle feat-opt"><input type="checkbox" id="ofFeatured"> <span>${t('of.feature', { p: rupees(PRICE) })}</span></label>` : ''}
      <button class="btn primary block" type="submit">${t('of.send')}</button>
      <p class="fine">${t('of.how')}</p>
    </form>`,
  (el) => {
    const ph = $('#ofPhone', el);
    ph.oninput = () => { const v = digits10(ph.value); if (v !== ph.value) ph.value = v; };
    $('#offerForm', el).onsubmit = async (e) => {
      e.preventDefault();
      const o = { placeId: id, title: $('#ofTitle', el).value.trim(), details: $('#ofDetails', el).value.trim(),
        from: $('#ofFrom', el).value, to: $('#ofTo', el).value, name: $('#ofName', el).value.trim(), phone: digits10(ph.value),
        featured: !!$('#ofFeatured', el)?.checked };
      if (!/^[6-9]\d{9}$/.test(o.phone)) { ph.focus(); return toast(t('pr.badPhone')); }
      if (o.to < o.from) return toast(t('of.err.bad_dates'));
      const b = e.target.querySelector('button[type=submit]'); b.disabled = true;
      try {
        const r = await community.submitOffer(o);
        if (r.status === 'pending') {
          track('offer', { place: id, kind: 'food', d: o.featured ? 'featured' : 'free' });
          if (o.featured) return paySheet(id, r.id);
          toast(t('of.sent'), 5000); return foodSheet(id);
        }
        toast(t(['bad_phone', 'bad_title', 'bad_name', 'bad_dates', 'rate_limited'].includes(r.status) ? 'of.err.' + r.status : 'of.err.other'));
      } catch { toast(t('sy.failed')); }
      b.disabled = false;
    };
  });
}
