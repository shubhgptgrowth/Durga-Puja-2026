/* "I parked here": save the car's spot with one tap, then walk back to it later. On Home and in Explore → Parking. */
import { S, t, store, loc, esc } from './state.js';
import { getFix, toast } from './ui.js';
import { hav } from './core.js';
import { dist, plain } from './state.js';
import { dirUrl } from './sheets.js';
import { tilePhoto, photoBg } from './photos.js';
import { track } from './analytics.js';

export function carCardHtml() {
  const car = S.car;
  if (!car) {
    return `<div class="car-card">${photoBg(tilePhoto('parking'), 'car-img')}
      <div class="car-tx"><b>${plain(t('car.title'))}</b><span>${t('car.sub')}</span></div>
      <button type="button" class="btn car-save" data-car="save">📍 ${t('car.save')}</button></div>`;
  }
  const when = new Date(car.ts).toLocaleString(loc(), { weekday: 'short', hour: 'numeric', minute: '2-digit' });
  return `<div class="car-card saved">${photoBg(tilePhoto('parking'), 'car-img')}
    <div class="car-tx"><b>${plain(t('car.yours'))}</b><span>${t('car.saved', { when: esc(when) })}${S.me ? ` · ${dist(hav(S.me, [car.lat, car.lng]))}` : ''}</span></div>
    <div class="car-btns"><a class="btn car-save" data-car="walk" target="_blank" rel="noopener" href="${dirUrl([car.lat, car.lng])}">🚶 ${t('car.walkBack')}</a>
      <button type="button" class="btn sm ghost" data-car="clear">${t('car.clear')}</button></div></div>`;
}

/** Handle a click inside a car card. Returns true when it was one. */
export function carClick(e, rerender) {
  const a = e.target.closest('[data-car]')?.dataset.car; if (!a) return false;
  if (a === 'clear') { S.car = null; store.set('car', null); rerender(); }
  if (a === 'walk') track('directions', { kind: 'parking', d: 'to_car' });
  if (a === 'save') {
    const b = e.target.closest('[data-car]'); b.disabled = true; b.textContent = t('v.locating');
    getFix().then((p) => { S.car = { lat: p.lat, lng: p.lng, ts: Date.now() }; store.set('car', S.car); track('filter', { d: 'car_saved' }); toast(t('car.savedToast')); rerender(); })
      .catch(() => { toast(t('loc.fail')); rerender(); });
  }
  return true;
}
