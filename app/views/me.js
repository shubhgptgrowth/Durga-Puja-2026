/* Me: walk tracker, my pujo (visits and food), badges, history and settings. */
import { S, G, idx, t, store, community, ll, nm, dn, esc, km, fmt, walkM, kcalFor, todayKey, savePrefs, icon, btn, loc,
} from '../state.js';
import { $, registerView, toast } from '../ui.js';
import { CONFIG } from '../config.js';
import { badgeSheet } from '../badges.js';
import { creditsHtml, wireCredits } from '../credits.js';
import { openPlace, dirUrl } from '../sheets.js';
import { BADGES, earned, daySteps, dayDist, dayWalkMin, startWalk, stopWalk, walking, motionLive, dayRec, saveHistory } from '../actions.js';
import { stopsOf, planValid } from './plan.js';
import { shareCard, myCard, appLink, myName, deviceId } from '../growth.js';
import { pujoCode, restoreLink, claimCode, signOutHere } from '../sync.js';

const isIOS = () => /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const syncUrl = () => `${location.origin}${location.pathname}?src=ios_shortcut#steps=`;

/** Ten digits of an Indian mobile number from whatever was typed or pasted (+91, 0, spaces, dashes). */
function digits10(v) {
  let d = String(v || '').replace(/\D/g, '');
  if (d.length > 10 && d.startsWith('91')) d = d.slice(2);
  else if (d.length > 10 && d.startsWith('0')) d = d.slice(1);
  return d.slice(0, 10);
}
const phoneOk = (d) => /^[6-9]\d{9}$/.test(d);
function phoneHint(el, final = false) {
  const d = $('#cPhone', el).value, h = $('#phoneHint', el);
  const bad = d && (/^[0-5]/.test(d) || (final || d.length === 10) && !phoneOk(d));
  h.textContent = !d ? '' : bad ? t('pr.badPhone') : d.length < 10 ? t('pr.moreDigits', { n: 10 - d.length }) : '✓';
  h.className = 'hint ' + (bad ? 'bad' : d.length === 10 ? 'ok' : '');
  $('#cPhone', el).setAttribute('aria-invalid', String(!!bad));
  return !d || phoneOk(d);
}

function profileHtml() {
  const p = S.prefs, name = myName();
  const open = openState?.['profile-box'] ?? !name;
  return `<details class="more profile-box pad-x" ${open ? 'open' : ''}>
    <summary>${name ? t('pr.hi', { name: esc(name) }) : `👋 ${t('pr.title')}`}</summary>
    <form id="contactForm" class="form contact">
      <label class="field">${t('pr.name')}<input id="cName" name="name" autocomplete="name" maxlength="40" value="${esc(p.name || '')}" placeholder="${t('pr.namePh')}"></label>
      <label class="field">${t('pr.phone')}<span class="phone-in"><span class="cc">+91</span><input id="cPhone" name="tel" type="tel" autocomplete="tel-national" inputmode="numeric"
        pattern="[6-9][0-9]{9}" value="${esc(digits10(p.phone))}" placeholder="9830012345" aria-describedby="phoneHint"></span>
        <small id="phoneHint" class="hint"></small></label>
      ${community.enabled ? `<p class="fine share-note">${t('pr.shareNote')}${p.contactOk ? ` <button type="button" class="link-btn" id="cRemove">${t('pr.remove')}</button>` : ''}</p>` : ''}
      <button class="btn primary block" type="submit">${t('pr.save')}</button>
    </form>
    <p class="fine">${t('pr.why2')}</p>
  </details>`;
}

const G_LOGO = '<svg class="g-logo" viewBox="0 0 48 48" aria-hidden="true"><path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z"/></svg>';
let googleOn = null; // the project's Google sign-in switch, read once

/** Sign in with Google: progress follows the person to any phone or browser, automatically. */
function accountHtml() {
  if (!community.enabled || !googleOn) return '';
  const acc = community.account;
  if (acc) return `<div class="account-box pad-x signed"><span class="ab-ic" aria-hidden="true">${G_LOGO}</span>
    <div class="ab-txt"><b>${t('gs.signedIn')}</b><small>${esc(acc.email || '')} · ${t('gs.synced')}</small></div>
    <button type="button" class="link-btn" id="gSignOut">${t('gs.signOut')}</button></div>`;
  return `<div class="account-box pad-x"><div class="ab-txt"><b>${t('gs.title')}</b><small>${t('gs.why')}</small></div>
    <button type="button" class="btn g-btn block" id="gSignIn">${G_LOGO}<span>${t('gs.continue')}</span></button></div>`;
}

/** My Pujo on another phone or browser: this browser's Pujo code, its link, and a box to enter another one. */
function syncHtml() {
  if (!community.enabled) return '';
  const code = pujoCode();
  return `<details class="more sync-box pad-x" ${openState?.['sync-box'] ? 'open' : ''}>
    <summary>🔁 ${t('sy.title')}</summary>
    <div class="sync-body">
      <p class="fine">${t('sy.why')}</p>
      ${code ? `<div class="pujo-code" aria-label="${t('sy.yourCode')}"><small>${t('sy.yourCode')}</small><b id="pujoCode">${esc(code)}</b></div>
        <div class="btn-row"><button class="btn sm primary" type="button" id="syShare">🔗 ${t('sy.share')}</button><button class="btn sm" type="button" id="syCopy">${t('sy.copy')}</button></div>
        <p class="fine">${t('sy.keep')}</p>` : `<p class="fine">${t('sy.noneYet')}</p>`}
      <form id="syncForm" class="hs-row"><input id="syCode" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="14" placeholder="PUJO-XXXX-XXXX" aria-label="${t('sy.enter')}">
        <button class="btn sm" type="submit">${t('sy.restore')}</button></form>
      <p class="fine">${t('sy.enterHint')}</p>
    </div>
  </details>`;
}

function iosHtml() {
  const link = CONFIG.healthShortcut; // set by scripts/sign_shortcut.sh, or an iCloud link
  return `<div class="ios-sync"><h4>${t('hs.iosTitle')}</h4>
    ${link ? `<a class="btn sm primary" href="${esc(link)}" target="_blank" rel="noopener">${t('hs.iosAdd')}</a><p class="fine">${t('hs.iosAuto')}</p>`
    : `<ol class="fine">${['hs.ios1', 'hs.ios2', 'hs.ios3', 'hs.ios4'].map((k) => `<li>${t(k)}</li>`).join('')}</ol>
      <div class="hs-row"><input readonly id="syncUrl" value="${esc(syncUrl())}" aria-label="${t('hs.iosUrl')}"><button class="btn sm" type="button" id="copySync">${t('hs.copy')}</button></div>
      <p class="fine">${t('hs.iosAuto')}</p>`}
  </div>`;
}

function nextStop() {
  if (!planValid(S.plan)) return '';
  const stops = stopsOf(S.plan), next = stops.find((x) => !S.checkins[x.pandal]);
  if (!next) return t('fit.planDone');
  const p = idx.pandal[next.pandal], done = stops.length - stops.filter((x) => !S.checkins[x.pandal]).length;
  return `${t('fit.next', { d: done, n: stops.length, name: `<b>${esc(nm(p))}</b>` })}${S.me ? ` · ${km(walkM(S.me, ll(p)))} km` : ''} <a href="${dirUrl(ll(p))}" target="_blank" rel="noopener">${t('p.directions')}</a>`;
}

/* The step counter redraws this page up to once a second while the phone moves. Typed-but-unsaved text and
 * which sections are open must survive that, and while someone is typing only the numbers are updated. */
const drafts = {};
const openKeys = ['profile-box', 'sync-box', 'health-sync', 'settings'];
let openState = null;

function liveUpdate(el, d, steps, goal) {
  const C = 2 * Math.PI * 86;
  const set = (sel, v) => { const n = $(sel, el); if (n) n.textContent = v; };
  set('#fitSteps', fmt(steps)); set('#fitKm', km(dayDist(d))); set('#fitPandals', d.pandals.length);
  const ring = $('.ring-fg', el); if (ring) ring.style.strokeDashoffset = C * (1 - Math.min(1, steps / goal));
}

function render() {
  const el = $('#view-me');
  if (googleOn === null && community.enabled) { googleOn = false; community.googleEnabled().then((v) => { if (v) { googleOn = true; render(); } }); }
  const d = S.history[todayKey()] || { m: 0, ms: 0, pandals: [], foods: [] };
  const steps = daySteps(d), goal = S.prefs.goal, mins = dayWalkMin(d), C = 2 * Math.PI * 86;
  const typing = el.contains(document.activeElement) && document.activeElement.matches('input, select, textarea');
  if (typing && $('#fitSteps', el)) return liveUpdate(el, d, steps, goal);
  if ($('#fitSteps', el)) openState = Object.fromEntries(openKeys.map((k) => [k, !!$(`details.${k}`, el)?.open]));
  const got = earned(), live = walking();
  const visited = Object.entries(S.checkins).sort((a, b) => b[1].ts - a[1].ts).map(([id]) => idx.pandal[id]).filter(Boolean);
  const foods = [...new Set(Object.values(S.history).flatMap((r) => r.foods || []))].map((id) => idx.food[id]).filter(Boolean);
  const rows = Object.entries(S.history).sort((a, b) => b[0].localeCompare(a[0]));
  const dayName = (date) => { const pd = G.data.meta.days.find((x) => x.date === date); return pd ? dn(pd) : new Date(date + 'T00:00').toLocaleDateString(loc(), { day: 'numeric', month: 'short' }); };
  const status = S.walk?.status || nextStop() || (live ? t('fit.live') : t('fit.idle'));

  el.innerHTML = `<section class="me-hero">
    <div class="me-hi"><h2>${myName() ? t('me.hiName', { name: esc(myName()) }) : t('me.title')}</h2><p>${t('me.subtitle')}</p></div>
    <div class="ring-wrap"><svg class="ring" viewBox="0 0 200 200" aria-hidden="true"><circle class="ring-bg" cx="100" cy="100" r="86"/><circle class="ring-fg" cx="100" cy="100" r="86" style="stroke-dashoffset:${C * (1 - Math.min(1, steps / goal))}"/></svg>
      <div class="ring-center" aria-live="polite"><div class="ring-steps" id="fitSteps">${fmt(steps)}</div><div class="ring-goal">${t('fit.of', { n: fmt(goal) })}</div></div></div>
    <p class="fit-src" id="fitSource">${live ? (motionLive() ? t('fit.src.motion') : t('fit.src.gps')) : ''}</p>
    <div class="stats4">
      <div class="s-km"><i aria-hidden="true">👣</i><b id="fitKm">${km(dayDist(d))}</b><span>${t('fit.km')}</span></div>
      <div class="s-kcal"><i aria-hidden="true">🔥</i><b>${fmt(kcalFor(mins))}</b><span>${t('fit.kcal')}</span></div>
      <div class="s-time"><i aria-hidden="true">⏱️</i><b>${Math.floor(mins / 60)}:${String(Math.floor(mins % 60)).padStart(2, '0')}</b><span>${t('fit.walking')}</span></div>
      <div class="s-pandal"><i aria-hidden="true">🛕</i><b id="fitPandals">${d.pandals.length}</b><span>${t('fit.pandals')}</span></div>
    </div>
    <button class="btn ${live ? 'live' : 'gold'} block" id="walkBtn">${live ? `<span class="pulse"></span> ${t('fit.tracking')}` : `${icon('walk')} ${store.get('walking', false) ? t('fit.resume') : t('fit.start')}`}</button>
    <p class="walk-status" id="walkStatus">${status}</p>
    </section>
    ${accountHtml()}
    ${profileHtml()}
    ${syncHtml()}

    <details class="more health-sync pad-x" ${openState?.['health-sync'] ? 'open' : ''}>
      <summary>⌚ ${t('hs.title')}${d.health ? ` · ${fmt(d.health)}` : ''}</summary>
      <div class="hs-body">
        <p class="fine">${t('hs.why')}</p>
        <form id="healthForm" class="hs-row"><input id="healthSteps" type="number" inputmode="numeric" min="0" max="100000" placeholder="${t('hs.ph')}" value="${d.health || ''}" aria-label="${t('hs.ph')}">
          <button class="btn primary sm" type="submit">${t('hs.save')}</button></form>
        <p class="fine">${t('hs.where')}</p>
        ${isIOS() || !/Android/.test(navigator.userAgent) ? iosHtml() : ''}
      </div>
    </details>

    <div class="pad" style="margin-top:6px"><button class="btn block story-btn" id="myCardBtn">📸 ${t('g.myCard')}</button><p class="fine center">${t('g.myCardSub')}</p></div>

    <section class="section"><div class="section-head"><h2>${t('me.visited', { n: visited.length })}</h2></div>
      ${visited.length ? `<div class="chips wrap pad">${visited.map((p) => `<button class="chip" data-place="${p.id}">${S.checkins[p.id].how === 'manual' ? '' : icon('check', 'sm')} ${esc(nm(p))}</button>`).join('')}</div>` : `<p class="fine pad">${t('me.noVisits')}</p>`}
      ${foods.length ? `<div class="section-head" style="margin-top:14px"><h2>${t('me.ate', { n: foods.length })}</h2></div><div class="chips wrap pad">${foods.map((f) => `<button class="chip" data-place="${f.id}">${icon('food', 'sm')} ${esc(f.name)}</button>`).join('')}</div>` : ''}
    </section>

    <section class="section"><div class="section-head"><h2>${t('fit.badges')}</h2><span class="fine">${got.size}/${BADGES.length}</span></div>
      <ul class="badges">${BADGES.map((x) => `<li><button type="button" class="badge-tile ${got.has(x.id) ? 'got' : ''}" data-badge="${x.id}"><span class="em" aria-hidden="true">${x.em}</span>${esc(S.prefs.lang === 'bn' ? x.bn : x.name)}<br><small class="fine">${got.has(x.id) ? `📸 ${t('bd.tapShare')}` : t('b.' + x.id)}</small></button></li>`).join('')}</ul></section>

    <section class="section"><div class="section-head"><h2>${t('fit.days')}</h2></div>
      <ul class="rows">${rows.map(([date, r]) => `<li><span><b>${esc(dayName(date))}</b> · ${t('fit.dayRow', { n: (r.pandals || []).length })}</span><span>${t('fit.dayStats', { s: fmt(daySteps(r)), km: km(dayDist(r)) })}</span></li>`).join('') || `<li><span class="fine">${t('fit.noDays')}</span></li>`}</ul></section>

    <details class="settings" ${openState?.settings ? 'open' : ''}><summary>${t('fit.settings')}</summary>
      <form id="profileForm" class="form grid2">
        <label>${t('fit.height')}<input type="number" id="pHeight" min="100" max="230" inputmode="numeric" value="${S.prefs.height}"></label>
        <label>${t('fit.weight')}<input type="number" id="pWeight" min="25" max="200" inputmode="numeric" value="${S.prefs.weight}"></label>
        <label>${t('fit.goal')}<input type="number" id="pGoal" min="1000" max="60000" step="500" inputmode="numeric" value="${S.prefs.goal}"></label>
        <label class="toggle"><input type="checkbox" id="pLowData" ${S.prefs.lowData ? 'checked' : ''}> <span>${t('fit.lowData')}</span></label>
        <label class="toggle" style="grid-column:1/-1"><input type="checkbox" id="pMotion" ${S.prefs.motion ? 'checked' : ''}> <span>${t('fit.motion')}</span></label>
        <button class="btn block" type="submit">${t('fit.save')}</button>
        <button class="btn ghost block" type="button" id="resetBtn">${t('fit.reset')}</button>
      </form>
      <p class="fine pad" style="margin-top:10px">${community.enabled ? t('me.privacyOn') : t('me.privacyOff')}</p>
    </details>
    ${creditsHtml()}`;

  wireCredits(el);
  for (const [id, v] of Object.entries(drafts)) { const f = $('#' + id, el); if (f) f.type === 'checkbox' ? (f.checked = v) : (f.value = v); }
  el.oninput = el.onchange = (e) => {
    if (e.target.id === 'cPhone') { const v = digits10(e.target.value); if (v !== e.target.value) e.target.value = v; phoneHint(el); }
    if (e.target.id && e.target.closest('form')) drafts[e.target.id] = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
  };
  if ($('#cPhone', el)?.value) phoneHint(el);
  const clearDrafts = (form) => form.querySelectorAll('[id]').forEach((f) => delete drafts[f.id]);
  el.onclick = async (e) => {
    if (e.target.closest('#cRemove')) {
      try { await community.saveProfile(null, null, false); } catch { /* offline: the flag below keeps trying on the next save */ }
      Object.assign(S.prefs, { phone: '', contactOk: false }); savePrefs(); delete drafts.cPhone;
      toast(t('pr.erased')); return render();
    }
    if (e.target.closest('#gSignIn')) {
      const b = e.target.closest('#gSignIn'); b.disabled = true;
      try { await community.signInWithGoogle(); } catch { b.disabled = false; toast(t('sy.failed')); }
      return;
    }
    if (e.target.closest('#gSignOut')) { if (confirm(t('gs.confirmOut'))) await signOutHere(); return; }
    if (e.target.closest('#syCopy')) { navigator.clipboard?.writeText(pujoCode()).then(() => toast(t('share.copied')), () => {}); return; }
    if (e.target.closest('#syShare')) {
      const text = t('sy.shareText', { code: pujoCode() }), url = restoreLink();
      if (navigator.share) return navigator.share({ title: t('sy.title'), text, url }).catch(() => {});
      navigator.clipboard?.writeText(`${text}\n${url}`).then(() => toast(t('share.copied')), () => {}); return;
    }
    if (e.target.closest('#walkBtn')) return walking() ? stopWalk() : startWalk();
    if (e.target.closest('#myCardBtn')) return shareCard(myCard(), `${myName() ? t('g.inviteFrom', { name: myName() }) : t('g.inviteText')}\n${appLink('ig_mycard')}`, 'my-pujo-2026.png');
    if (e.target.closest('#copySync')) { const i = $('#syncUrl', el); i.select(); navigator.clipboard?.writeText(i.value).then(() => toast(t('share.copied')), () => {}); return; }
    const bd = e.target.closest('[data-badge]')?.dataset.badge; if (bd) return badgeSheet(bd);
    const pl = e.target.closest('[data-place]')?.dataset.place; if (pl) return openPlace(pl);
    if (e.target.closest('#resetBtn') && confirm(t('fit.confirmReset'))) { store.clear(); location.reload(); }
  };
  const syf = $('#syncForm', el);
  if (syf) syf.onsubmit = async (e) => {
    e.preventDefault();
    const code = $('#syCode', el).value.trim(); if (!code) return $('#syCode', el).focus();
    if (code.toUpperCase().replace(/[^A-Z0-9]/g, '') === (pujoCode() || '').replace(/-/g, '')) return toast(t('sy.same'));
    clearDrafts(e.target); await claimCode(code);
  };
  $('#healthForm', el).onsubmit = (e) => {
    e.preventDefault();
    const n = Math.max(0, Math.min(100000, Math.round(+$('#healthSteps', el).value || 0)));
    const r = dayRec(); r.health = n; saveHistory(); clearDrafts(e.target); toast(t('hs.saved', { n: fmt(n) })); render();
  };
  $('#contactForm', el).onsubmit = async (e) => {
    e.preventDefault();
    const name = $('#cName', el).value.trim().slice(0, 40), phone = digits10($('#cPhone', el).value);
    // Saving a number shares it with the team (the note above the button says so); no number, nothing is shared.
    const consent = community.enabled && !!phone, wasOk = S.prefs.contactOk;
    if (!phoneHint(el, true)) { $('#cPhone', el).focus(); return toast(t('pr.badPhone')); }
    Object.assign(S.prefs, { name, phone, contactOk: consent }); savePrefs(); clearDrafts(e.target);
    $('details.profile-box', el).open = false; // saved: fold it away, the summary shows the name
    if (community.enabled && (consent || wasOk)) {
      try {
        const r = await community.saveProfile(name, phone, consent, { lang: S.prefs.lang, src: store.get('firstSrc', S.src || 'direct'), device: deviceId() });
        toast(t(r.status === 'deleted' ? 'pr.erased' : r.status === 'ok' ? 'pr.savedShared' : 'pr.badPhone'));
      } catch { toast(t('pr.savedLocal')); }
    } else toast(t('pr.savedLocal'));
    render();
  };
  $('#profileForm', el).onsubmit = (e) => {
    e.preventDefault();
    const lowBefore = S.prefs.lowData;
    Object.assign(S.prefs, { height: +$('#pHeight').value || 165, weight: +$('#pWeight').value || 65, goal: +$('#pGoal').value || 10000,
      lowData: $('#pLowData').checked, motion: $('#pMotion').checked });
    savePrefs(); clearDrafts(e.target); toast(t('fit.savedToast')); render();
    if (lowBefore !== S.prefs.lowData) location.reload();
  };
}

registerView('me', { render });
