/* Detail sheets: pandal, eatery, parking, moment viewer, and the upload flow. */
import { hav, fmtCount, isOpen, nearest, timeAgo } from './core.js';
import {
  S, G, idx, t, store, community, ll, M, nm, zn, dn, zoneOf, placeOf, placeKind, esc, km, dist, ampm,
  crowdIndex, crowdWord, crowdColor, crowdLevel, dayFactor, btn, icon, savePrefs,
} from './state.js';
import { openSheet, closeSheet, toast, go, getFix, rerender, $ } from './ui.js';
import { visit, visitPrivately, visitMessage, visitedToday } from './actions.js';
import { prepareMedia } from './media.js';
import { CONFIG } from './config.js';

export const dirUrl = (dest, mode = 'walking') => `https://www.google.com/maps/dir/?api=1&destination=${dest[0]},${dest[1]}&travelmode=${mode}`;

/* ---------------- shared bits ---------------- */
export function statsHtml(id, { compact = false } = {}) {
  const s = community.enabled ? community.statFor(id) : null;
  if (!s) return '';
  const food = placeKind(id) === 'food';
  if (compact) {
    const live = s.last_hour >= 5 ? `<span class="pill live"><span class="dot"></span>${t('c.liveN', { n: fmtCount(s.last_hour) })}</span>` : '';
    return `${live}<span class="count">${icon(food ? 'food' : 'people', 'sm')} ${fmtCount(s.visits)}</span>`;
  }
  return `<div class="stat-row">
    <div class="stat"><b>${fmtCount(s.visits)}</b><span>${t(food ? 'c.ate' : 'c.visits')}</span></div>
    <div class="stat"><b>${fmtCount(s.today)}</b><span>${t('c.today')}</span></div>
    <div class="stat"><b>${s.last_hour >= 1 ? fmtCount(s.last_hour) : fmtCount(s.photos)}</b><span>${s.last_hour >= 1 ? t('c.lastHour') : t('c.moments')}</span></div>
  </div>`;
}
export const crowdPill = (c) => `<span class="pill ${crowdLevel(c)}"><span class="dot"></span>${crowdWord(c)}</span>`;
export function agoText(iso) {
  const a = timeAgo(iso);
  return a.unit === 'now' ? t('ago.now') : t('ago.' + a.unit, { n: a.n });
}
export function thumbHtml(m) {
  return `<button class="thumb" data-moment="${m.id}" aria-label="${esc(nm(placeOf(m.place_id) || { name: '' }))}">
    <img loading="lazy" decoding="async" src="${community.mediaUrl(m.thumb_path)}" alt="">
    ${m.media_type === 'video' ? `<span class="vid">${icon('play', 'fill')}</span>` : ''}
    ${m.likes ? `<span class="badge">${icon('heart', 'sm fill')} ${fmtCount(m.likes)}</span>` : ''}
  </button>`;
}

async function placeMoments(el, id) {
  const box = $('[data-moments]', el);
  if (!box || !community.enabled) return;
  try {
    const items = await community.feed({ placeIds: [id], limit: 9 });
    momentCache.push(...items);
    box.innerHTML = items.length ? `<div class="grid-photos compact">${items.map(thumbHtml).join('')}</div>` : `<p class="fine">${t('m.noneHere')}</p>`;
    box.onclick = (e) => { const b = e.target.closest('[data-moment]'); if (b) momentSheet(momentCache.find((m) => m.id === b.dataset.moment)); };
  } catch { box.innerHTML = `<p class="fine">${t('m.offline')}</p>`; }
}
export const momentCache = [];

function visitButton(id) {
  const food = placeKind(id) === 'food';
  const done = visitedToday(id);
  return `<button class="btn ${done ? 'success' : 'primary'}" id="visitBtn" ${done ? 'disabled' : ''}>
    ${icon(food ? 'food' : 'check')} ${done ? t(food ? 'v.ateDone' : 'v.done') : t(food ? 'v.ate' : 'v.checkin')}</button>`;
}
function wireVisit(el, id, reopen) {
  const b = $('#visitBtn', el); if (!b) return;
  b.onclick = async () => {
    b.disabled = true; b.innerHTML = `${icon('locate')} ${t('v.locating')}`;
    const r = await visit(id);
    if (!['too_far', 'no_fix', 'denied'].includes(r.status)) toast(visitMessage(id, r), 3500);
    if (r.status === 'too_far' || r.status === 'no_fix' || r.status === 'denied') {
      const v = $('#verifyBox', el);
      v.innerHTML = `<div class="notice limited"><b>${visitMessage(id, r)}</b><span>${t('v.privateHint')}</span>
        <button class="btn sm" id="privBtn">${t('v.private')}</button></div>`;
      $('#privBtn', el).onclick = () => { visitPrivately(id); reopen(); rerender(); };
      b.disabled = false; b.innerHTML = `${icon('check')} ${t('v.retry')}`;
      return;
    }
    reopen(); rerender();
  };
}

/* ---------------- pandal ---------------- */
export function pandalSheet(id) {
  const p = idx.pandal[id], z = zoneOf(p.zone), df = dayFactor();
  const hours = [...Array(24).keys()].map((h) => crowdIndex(p.crowd_base, df, h));
  const now = hours[S.hour];
  const foods = p.food.map((f) => ({ ...idx.food[f.id], ...f }));
  const parks = p.parking.map((x) => ({ ...idx.parking[x.id], ...x }));
  const away = S.me ? ` · ${dist(hav(S.me, ll(p)))}` : '';
  openSheet(`
    <div class="eyebrow"><span class="dot" style="background:${z.color}"></span>${esc(zn(z))}${away}</div>
    <h2 class="title">${esc(nm(p))}</h2>
    <div class="fine">${S.prefs.lang === 'bn' ? esc(p.name) : esc(p.name_bn || '')}</div>
    <div class="btn-row" style="margin-top:8px">${crowdPill(now)}<span class="pill">${icon('star', 'sm fill')} ${p.popularity}/5</span><span class="pill">${icon('clock', 'sm')} ${t('slot.' + p.best_slot)}</span></div>
    ${statsHtml(id)}
    <div class="btn-row" style="margin-top:12px">
      ${visitButton(id)}
      <a class="btn" target="_blank" rel="noopener" href="${dirUrl(ll(p))}">${icon('pin')} ${t('p.directions')}</a>
    </div>
    <div id="verifyBox" class="verify"></div>
    <p class="lead">${esc(p.highlight)}</p>

    <h3 class="sh">${t('p.when', { day: dn(idx.day[S.day]) })}</h3>
    <div class="hours" role="img" aria-label="${t('p.crowdChart')}">${hours.map((c, h) => `<i class="${h === S.hour ? 'now' : ''}" style="height:${Math.max(c, 4)}%;background:${crowdColor(c)}" title="${ampm(h)}: ${crowdWord(c)}"></i>`).join('')}</div>
    <div class="hours-axis" aria-hidden="true"><span>12a</span><span>6a</span><span>12p</span><span>6p</span><span>11p</span></div>
    <p class="small muted" style="margin:6px 0 0">${t('p.quietest')}: <b>${p.quiet_hours[S.day].map(ampm).join(', ')}</b> · ${t('p.inside', { n: p.visit_min })}</p>

    <h3 class="sh">${t('p.getThere')}</h3>
    <ul class="mini-list">
      <li data-act="metro"><span>${icon('metro', 'sm')} <span class="line-${p.nearest_metro.line}">●</span> ${esc(p.nearest_metro.name)}</span><small>${t('p.walkMin', { n: p.nearest_metro.walk_min })}</small></li>
      ${parks.map((x) => `<li data-park="${x.id}" ${btn()}><span>${icon('car', 'sm')} ${esc(x.name)}</span><small>${km(x.distance_m)} km</small></li>`).join('')}
    </ul>
    ${z.car_advisory !== 'ok' ? `<p class="fine" style="margin-top:6px">${esc(z.walk_tip)}</p>` : ''}

    <h3 class="sh">${t('p.eat')}</h3>
    <ul class="mini-list">${foods.map((f) => `<li data-food="${f.id}" ${btn()}><span><b>${esc(f.name)}</b><br><small>${esc(f.dishes.slice(0, 2).join(' · '))}</small></span><small>${t('p.walkMin', { n: f.walk_min })}</small></li>`).join('') || `<li>${t('p.noeat')}</li>`}</ul>

    ${community.enabled ? `<h3 class="sh" style="display:flex;justify-content:space-between;align-items:center">${t('m.here')}<button class="link-btn" id="addMomentBtn">${icon('camera', 'sm')} ${t('m.add')}</button></h3><div data-moments><p class="fine">${t('m.loading')}</p></div>` : ''}
    <p class="fine" style="margin-top:16px">${t('p.disclaimer')}</p>`,
  (el) => {
    wireVisit(el, id, () => pandalSheet(id));
    el.querySelectorAll('[data-food]').forEach((li) => (li.onclick = () => foodSheet(li.dataset.food)));
    el.querySelectorAll('[data-park]').forEach((li) => (li.onclick = () => parkSheet(li.dataset.park)));
    const add = $('#addMomentBtn', el); if (add) add.onclick = () => uploadSheet({ placeId: id });
    placeMoments(el, id);
  });
}

/* ---------------- eatery ---------------- */
export function foodSheet(id) {
  const f = idx.food[id], z = zoneOf(f.zone);
  const away = S.me ? ` · ${dist(hav(S.me, ll(f)))}` : '';
  openSheet(`
    <div class="eyebrow"><span class="dot" style="background:${z.color}"></span>${esc(zn(z))} · ${t('type.' + f.type)}${away}</div>
    <h2 class="title">${esc(f.name)}</h2>
    <div class="btn-row" style="margin-top:8px"><span class="pill ${isOpen(f.hours) ? 'ok' : ''}">${isOpen(f.hours) ? t('food.open') : t('food.closed')} · ${esc(f.hours)}</span><span class="pill">${'₹'.repeat(f.price)}</span><span class="pill">${t('diet.' + f.veg)}</span></div>
    ${statsHtml(id)}
    <div class="btn-row" style="margin-top:12px">
      ${visitButton(id)}
      <a class="btn" target="_blank" rel="noopener" href="${dirUrl(ll(f))}">${icon('pin')} ${t('p.directions')}</a>
    </div>
    <div id="verifyBox" class="verify"></div>
    <p class="lead">${esc(f.note)}</p>
    <h3 class="sh">${t('food.mustTry')}</h3>
    <div class="btn-row">${f.dishes.map((d) => `<span class="pill">${esc(d)}</span>`).join('')}</div>
    <h3 class="sh">${t('food.walkable')}</h3>
    <ul class="mini-list">${f.near_pandals.map((pid) => `<li data-p="${pid}" ${btn()}><b>${esc(nm(idx.pandal[pid]))}</b><small>${dist(hav(ll(f), ll(idx.pandal[pid])))}</small></li>`).join('') || `<li>${t('food.noneNear')}</li>`}</ul>
    ${community.enabled ? `<h3 class="sh" style="display:flex;justify-content:space-between;align-items:center">${t('m.here')}<button class="link-btn" id="addMomentBtn">${icon('camera', 'sm')} ${t('m.add')}</button></h3><div data-moments><p class="fine">${t('m.loading')}</p></div>` : ''}
    <p class="fine" style="margin-top:16px">${t('food.hoursNote')}</p>`,
  (el) => {
    wireVisit(el, id, () => foodSheet(id));
    el.querySelectorAll('[data-p]').forEach((li) => (li.onclick = () => pandalSheet(li.dataset.p)));
    const add = $('#addMomentBtn', el); if (add) add.onclick = () => uploadSheet({ placeId: id });
    placeMoments(el, id);
  });
}

/* ---------------- parking ---------------- */
export function parkSheet(id) {
  const p = idx.parking[id];
  const pandals = nearest(ll(p), G.data.pandals, { maxM: 2000, limit: 5 });
  openSheet(`<div class="eyebrow">${icon('car', 'sm')} ${t('kind.' + p.kind)}</div>
    <h2 class="title">${esc(p.name)}</h2>
    <p class="lead">${esc(p.note)}</p>
    <dl class="kv" style="margin-top:12px"><dt>${t('park.size')}</dt><dd>${esc(p.capacity)}</dd><dt>${t('park.rate')}</dt><dd>${esc(p.rate_hint)} ${t('park.approx')}</dd></dl>
    <div class="btn-row" style="margin-top:12px"><a class="btn primary" target="_blank" rel="noopener" href="${dirUrl(ll(p), 'driving')}">${icon('car')} ${t('park.drive')}</a></div>
    <h3 class="sh">${t('park.walkTo')}</h3>
    <ul class="mini-list">${pandals.map(({ place: x, distance: d }) => `<li data-p="${x.id}" ${btn()}><b>${esc(nm(x))}</b><small>${dist(d * M().detour)}</small></li>`).join('') || `<li>${t('park.onward')}</li>`}</ul>`,
  (el) => el.querySelectorAll('[data-p]').forEach((li) => (li.onclick = () => pandalSheet(li.dataset.p))));
}

export function openPlace(id) {
  if (idx.pandal[id]) return pandalSheet(id);
  if (idx.food[id]) return foodSheet(id);
  if (idx.parking[id]) return parkSheet(id);
}

/* ---------------- moment viewer ---------------- */
export function momentSheet(m) {
  if (!m) return;
  const p = placeOf(m.place_id);
  const media = m.media_type === 'video'
    ? `<video src="${community.mediaUrl(m.path)}" poster="${community.mediaUrl(m.thumb_path)}" controls playsinline preload="metadata"></video>`
    : `<img src="${community.mediaUrl(m.path)}" alt="${esc(m.caption || nm(p))}">`;
  openSheet(`<div class="moment-view">${media}</div>
    <div class="moment-meta">
      <div><button class="link-btn" id="mPlace" style="font-size:16px">${esc(nm(p))} ${icon('chev', 'sm')}</button>
        <div class="fine">${agoText(m.created_at)}${m.on_site ? ` · <span class="pill ok">${icon('pin', 'sm')} ${t('m.onSite')}</span>` : ''}</div></div>
      <button class="btn sm like-btn" id="mLike" aria-pressed="${!!m.liked}">${icon('heart')} <span>${fmtCount(m.likes)}</span></button>
    </div>
    ${m.caption ? `<p class="lead" style="margin-top:4px">${esc(m.caption)}</p>` : ''}
    <div class="btn-row" style="margin-top:14px">
      ${m.mine ? `<button class="btn sm ghost" id="mDelete">${icon('trash', 'sm')} ${t('m.delete')}</button>` : `<button class="btn sm" id="mReport">${icon('flag', 'sm')} ${t('m.report')}</button>`}
    </div>`,
  (el) => {
    $('#mPlace', el).onclick = () => openPlace(m.place_id);
    $('#mLike', el).onclick = async (e) => {
      const b = e.currentTarget;
      try {
        const r = await community.toggleLike(m.id);
        m.liked = r.liked; m.likes = r.likes;
        b.setAttribute('aria-pressed', r.liked); b.querySelector('span').textContent = fmtCount(r.likes);
      } catch { toast(t('m.offline')); }
    };
    const rep = $('#mReport', el);
    if (rep) rep.onclick = async () => {
      if (!confirm(t('m.reportConfirm'))) return;
      try { const r = await community.report(m.id, 'user'); toast(t(r.status === 'already_reported' ? 'm.reportedAlready' : 'm.reported')); closeSheet(); }
      catch { toast(t('m.offline')); }
    };
    const del = $('#mDelete', el);
    if (del) del.onclick = async () => {
      if (!confirm(t('m.deleteConfirm'))) return;
      try { await community.deleteMoment(m.id); S.moments.items = S.moments.items.filter((x) => x.id !== m.id); toast(t('m.deleted')); closeSheet(); rerender(); }
      catch { toast(t('m.offline')); }
    };
  });
}

/* ---------------- upload ---------------- */
export function uploadSheet({ placeId = null } = {}) {
  if (!community.enabled) return toast(t('m.disabled'));
  let fix = null, prepared = null, chosen = placeId;
  const allPlaces = [...G.data.pandals, ...G.data.food];

  const placeOptions = (near) => {
    const list = near.length ? near.map((n) => n.place) : [];
    const rest = allPlaces.filter((p) => !list.includes(p)).sort((a, b) => nm(a).localeCompare(nm(b)));
    const opt = (p, d) => `<option value="${p.id}" ${p.id === chosen ? 'selected' : ''}>${esc(nm(p))}${d != null ? ` · ${dist(d)}` : ''}</option>`;
    return (near.length ? `<optgroup label="${t('m.nearby')}">${near.map((n) => opt(n.place, n.distance)).join('')}</optgroup>` : '')
      + `<optgroup label="${t('m.allPlaces')}">${rest.map((p) => opt(p)).join('')}</optgroup>`;
  };

  openSheet(`<h2 class="title">${t('m.addTitle')}</h2>
    <p class="fine" style="margin:4px 0 12px">${t('m.addSub')}</p>
    <div class="form" style="padding:0">
      <label>${t('m.where')}<select id="upPlace">${placeOptions([])}</select></label>
      <div class="upload-preview" id="upPreview">${icon('image')}</div>
      <div class="btn-row">
        <button class="btn" type="button" id="upCamera">${icon('camera')} ${t('m.camera')}</button>
        <button class="btn" type="button" id="upGallery">${icon('image')} ${t('m.gallery')}</button>
      </div>
      <label>${t('m.caption')}<textarea id="upCaption" maxlength="140" rows="2" placeholder="${t('m.captionPh')}"></textarea></label>
      ${S.prefs.consent ? '' : `<label class="toggle"><input type="checkbox" id="upConsent"> <span>${t('m.consent')}</span></label>`}
      <div class="progress" id="upProgress" hidden><i></i></div>
      <button class="btn primary block" id="upPost" disabled>${t('m.post')}</button>
      <p class="fine" id="upNote">${t('m.limits', { s: CONFIG.community.maxVideoSec, mb: CONFIG.community.maxVideoMB })}</p>
    </div>`,
  (el) => {
    const sel = $('#upPlace', el), post = $('#upPost', el);
    const ready = () => { post.disabled = !(prepared && sel.value && (S.prefs.consent || $('#upConsent', el)?.checked)); };
    sel.onchange = () => { chosen = sel.value; ready(); };
    $('#upConsent', el)?.addEventListener('change', ready);
    // Locate in the background: it sorts the nearby places first and tags the moment as on-site.
    getFix({ timeout: 10000, maximumAge: 0 }).then((f) => {
      fix = f;
      const near = nearest([f.lat, f.lng], allPlaces, { maxM: 1500, limit: 8 });
      if (!chosen && near[0]) chosen = near[0].place.id;
      sel.innerHTML = placeOptions(near); if (chosen) sel.value = chosen; ready();
    }).catch(() => { if (!chosen) chosen = sel.value; });
    const pick = (input) => { input.value = ''; input.onchange = async () => {
      const file = input.files[0]; if (!file) return;
      $('#upPreview', el).innerHTML = `<p class="fine">${t('m.preparing')}</p>`;
      try {
        prepared = await prepareMedia(file, { maxSec: CONFIG.community.maxVideoSec, maxMB: CONFIG.community.maxVideoMB });
        $('#upPreview', el).innerHTML = `<img src="${prepared.previewUrl}" alt="">${prepared.mediaType === 'video' ? `<span class="vid" style="position:absolute;right:10px;top:10px;color:#fff">${icon('play', 'fill')}</span>` : ''}`;
      } catch (e) {
        prepared = null;
        $('#upPreview', el).innerHTML = `<p class="fine" style="padding:16px">${t('m.err.' + (e.code || 'unsupported'), { s: CONFIG.community.maxVideoSec, mb: CONFIG.community.maxVideoMB })}</p>`;
      }
      ready();
    }; input.click(); };
    $('#upCamera', el).onclick = () => pick($('#pickCamera'));
    $('#upGallery', el).onclick = () => pick($('#pickGallery'));
    post.onclick = async () => {
      if ($('#upConsent', el)?.checked) { S.prefs.consent = true; savePrefs(); }
      post.disabled = true; post.textContent = t('m.posting');
      const bar = $('#upProgress', el); bar.hidden = false;
      try {
        const r = await community.addMoment({ placeId: sel.value, mediaType: prepared.mediaType, full: prepared.full, thumb: prepared.thumb, ext: prepared.ext,
          caption: $('#upCaption', el).value.trim(), fix }, (p) => { bar.firstElementChild.style.width = `${Math.round(p * 100)}%`; });
        if (r.status === 'ok') {
          store.set('myMoments', store.get('myMoments', 0) + 1);
          toast(r.on_site ? t('m.postedOnSite') : t('m.posted'), 3500);
          S.moments.items = []; S.moments.done = false;
          closeSheet(); go('moments');
        } else if (r.status === 'queued') { toast(t('m.queued'), 4000); closeSheet(); }
        else { toast(t('m.err.server', { s: r.status })); post.disabled = false; post.textContent = t('m.post'); }
      } catch { toast(t('m.err.server', { s: 'error' })); post.disabled = false; post.textContent = t('m.post'); }
    };
  });
}
