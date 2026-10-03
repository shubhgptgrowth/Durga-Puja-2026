/* Me: walk tracker, my pujo (visits and food), badges, history and settings. */
import { S, G, idx, t, store, community, ll, nm, dn, esc, km, fmt, walkM, kcalFor, todayKey, savePrefs, icon, btn, loc,
} from '../state.js';
import { $, registerView, toast } from '../ui.js';
import { CONFIG } from '../config.js';
import { openPlace, dirUrl } from '../sheets.js';
import { BADGES, earned, daySteps, dayDist, dayWalkMin, startWalk, stopWalk, walking, motionLive, dayRec, saveHistory } from '../actions.js';
import { stopsOf, planValid } from './plan.js';
import { shareCard, myCard, appLink, myName } from '../growth.js';

const isIOS = () => /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
const syncUrl = () => `${location.origin}${location.pathname}?src=ios_shortcut#steps=`;

function profileHtml() {
  const p = S.prefs, name = myName();
  return `<details class="more profile-box pad-x" ${name ? '' : 'open'}>
    <summary>${name ? t('pr.hi', { name: esc(name) }) : `👋 ${t('pr.title')}`}</summary>
    <form id="contactForm" class="form grid2">
      <label>${t('pr.name')}<input id="cName" name="name" autocomplete="name" maxlength="40" value="${esc(p.name || '')}" placeholder="${t('pr.namePh')}"></label>
      <label>${t('pr.phone')}<input id="cPhone" name="tel" type="tel" autocomplete="tel" inputmode="tel" maxlength="16" value="${esc(p.phone || '')}" placeholder="98300 12345"></label>
      ${community.enabled ? `<label class="toggle" style="grid-column:1/-1"><input type="checkbox" id="cConsent" ${p.contactOk ? 'checked' : ''}> <span>${t('pr.consent')}</span></label>` : ''}
      <button class="btn primary block" type="submit" style="grid-column:1/-1">${t('pr.save')}</button>
    </form>
    <p class="fine">${t('pr.why')}</p>
  </details>`;
}

function iosHtml() {
  const link = CONFIG.healthShortcut;
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

function render() {
  const el = $('#view-me');
  const d = S.history[todayKey()] || { m: 0, ms: 0, pandals: [], foods: [] };
  const steps = daySteps(d), goal = S.prefs.goal, mins = dayWalkMin(d), C = 2 * Math.PI * 86;
  const got = earned(), live = walking();
  const visited = Object.entries(S.checkins).sort((a, b) => b[1].ts - a[1].ts).map(([id]) => idx.pandal[id]).filter(Boolean);
  const foods = [...new Set(Object.values(S.history).flatMap((r) => r.foods || []))].map((id) => idx.food[id]).filter(Boolean);
  const rows = Object.entries(S.history).sort((a, b) => b[0].localeCompare(a[0]));
  const dayName = (date) => { const pd = G.data.meta.days.find((x) => x.date === date); return pd ? dn(pd) : new Date(date + 'T00:00').toLocaleDateString(loc(), { day: 'numeric', month: 'short' }); };
  const status = S.walk?.status || nextStop() || (live ? t('fit.live') : t('fit.idle'));

  el.innerHTML = `<div class="view-title"><h2>${t('me.title')}</h2><p>${t('me.subtitle')}</p></div>
    ${profileHtml()}
    <div class="ring-wrap"><svg class="ring" viewBox="0 0 200 200" aria-hidden="true"><circle class="ring-bg" cx="100" cy="100" r="86"/><circle class="ring-fg" cx="100" cy="100" r="86" style="stroke-dashoffset:${C * (1 - Math.min(1, steps / goal))}"/></svg>
      <div class="ring-center" aria-live="polite"><div class="ring-steps" id="fitSteps">${fmt(steps)}</div><div class="ring-goal">${t('fit.of', { n: fmt(goal) })}</div></div></div>
    <p class="fine center" id="fitSource">${live ? (motionLive() ? t('fit.src.motion') : t('fit.src.gps')) : ''}</p>
    <div class="stats4">
      <div><b id="fitKm">${km(dayDist(d))}</b><span>${t('fit.km')}</span></div>
      <div><b>${fmt(kcalFor(mins))}</b><span>${t('fit.kcal')}</span></div>
      <div><b>${Math.floor(mins / 60)}:${String(Math.floor(mins % 60)).padStart(2, '0')}</b><span>${t('fit.walking')}</span></div>
      <div><b id="fitPandals">${d.pandals.length}</b><span>${t('fit.pandals')}</span></div>
    </div>
    <div class="pad" style="margin-top:12px">
      <button class="btn ${live ? 'live' : 'primary'} block" id="walkBtn">${live ? `<span class="pulse"></span> ${t('fit.tracking')}` : `${icon('walk')} ${store.get('walking', false) ? t('fit.resume') : t('fit.start')}`}</button>
      <p class="fine center" id="walkStatus">${status}</p>
    </div>

    <details class="more health-sync pad-x">
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
      <ul class="badges">${BADGES.map((x) => `<li class="badge-tile ${got.has(x.id) ? 'got' : ''}"><span class="em" aria-hidden="true">${x.em}</span>${esc(S.prefs.lang === 'bn' ? x.bn : x.name)}<br><small class="fine">${t('b.' + x.id)}</small></li>`).join('')}</ul></section>

    <section class="section"><div class="section-head"><h2>${t('fit.days')}</h2></div>
      <ul class="rows">${rows.map(([date, r]) => `<li><span><b>${esc(dayName(date))}</b> · ${t('fit.dayRow', { n: (r.pandals || []).length })}</span><span>${t('fit.dayStats', { s: fmt(daySteps(r)), km: km(dayDist(r)) })}</span></li>`).join('') || `<li><span class="fine">${t('fit.noDays')}</span></li>`}</ul></section>

    <details class="settings"><summary>${t('fit.settings')}</summary>
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
    </details>`;

  el.onclick = (e) => {
    if (e.target.closest('#walkBtn')) return walking() ? stopWalk() : startWalk();
    if (e.target.closest('#myCardBtn')) return shareCard(myCard(), `${myName() ? t('g.inviteFrom', { name: myName() }) : t('g.inviteText')}\n${appLink('ig_mycard')}`, 'my-pujo-2026.png');
    if (e.target.closest('#copySync')) { const i = $('#syncUrl', el); i.select(); navigator.clipboard?.writeText(i.value).then(() => toast(t('share.copied')), () => {}); return; }
    const pl = e.target.closest('[data-place]')?.dataset.place; if (pl) return openPlace(pl);
    if (e.target.closest('#resetBtn') && confirm(t('fit.confirmReset'))) { store.clear(); location.reload(); }
  };
  $('#healthForm', el).onsubmit = (e) => {
    e.preventDefault();
    const n = Math.max(0, Math.min(100000, Math.round(+$('#healthSteps', el).value || 0)));
    const r = dayRec(); r.health = n; saveHistory(); toast(t('hs.saved', { n: fmt(n) })); render();
  };
  $('#contactForm', el).onsubmit = async (e) => {
    e.preventDefault();
    const name = $('#cName', el).value.trim().slice(0, 40), phone = $('#cPhone', el).value.trim();
    const consent = !!$('#cConsent', el)?.checked, wasOk = S.prefs.contactOk;
    const digits = phone.replace(/\D/g, '').replace(/^(91|0)(?=[6-9]\d{9}$)/, '');
    if (phone && !/^[6-9]\d{9}$/.test(digits)) return toast(t('pr.badPhone'));
    if (consent && !phone) return toast(t('pr.needPhone'));
    Object.assign(S.prefs, { name, phone, contactOk: consent }); savePrefs();
    if (community.enabled && (consent || wasOk)) {
      try {
        const r = await community.saveProfile(name, phone, consent);
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
    savePrefs(); toast(t('fit.savedToast')); render();
    if (lowBefore !== S.prefs.lowData) location.reload();
  };
}

registerView('me', { render });
