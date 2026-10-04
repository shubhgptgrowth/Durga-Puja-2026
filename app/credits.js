/* Photo and sound credits (Creative Commons licences need them), listed in My Pujo → Settings. */
import { t, esc } from './state.js';

let cache = null;
async function load() {
  const get = (u) => fetch(u).then((r) => r.json()).catch(() => null);
  const [heroes, tiles, audio] = await Promise.all([get('img/heroes.json'), get('img/tiles/tiles.json'), get('audio/credits.json')]);
  const clean = (s) => String(s || '').replace(/^File:/, '').replace(/\.\w+$/, '');
  return [...(heroes || []).map((x) => ({ ...x, kind: '📷' })), ...Object.values(tiles || {}).map((x) => ({ ...x, kind: '📷' })),
    ...Object.values(audio || {}).map((x) => ({ ...x, kind: '🔊' }))].map((x) => ({ ...x, title: clean(x.title) }));
}
export function creditsHtml() {
  return `<details class="credits-box"><summary>${t('cr.title')}</summary><ul class="credits" id="creditsList"><li class="fine">${t('m.loading')}</li></ul>
    <p class="fine">${t('cr.note')}</p></details>`;
}
export function wireCredits(el) {
  const d = el.querySelector('.credits-box'); if (!d) return;
  d.addEventListener('toggle', async () => {
    if (!d.open) return;
    cache ||= await load();
    el.querySelector('#creditsList').innerHTML = cache.map((x) => `<li>${x.kind} <a href="${esc(x.page)}" target="_blank" rel="noopener">${esc(x.title)}</a> · ${esc(x.author)} · ${esc(x.license)}</li>`).join('');
  }, { once: false });
}
