/* "Add a missing pujo": a short form that sends a suggestion to the team (supabase suggest_pujo, see
 * supabase/migrations/20261018000000_pujo_suggestions.sql). Name and area are required; a landmark, a note and
 * where you are standing (only if you tick it) help us pin it. No phone or e-mail is asked for. */
import { G, t, esc, zn, community } from './state.js';
import { openSheet, closeSheet, toast, getFix, $ } from './ui.js';
import { track } from './analytics.js';

export function suggestSheet({ name = '' } = {}) {
  if (!community.enabled) return toast(t('sy.off'));
  track('suggest_open');
  const areas = [...new Set(G.data.zones.map((z) => zn(z)))].sort();
  openSheet(`<div class="eyebrow">➕ ${t('sg.eyebrow')}</div>
    <h2 class="title">${t('sg.title')}</h2>
    <p class="fine" style="margin:4px 0 12px">${t('sg.sub')}</p>
    <form id="sgForm" class="form" style="padding:0">
      <label>${t('sg.name')}<input id="sgName" required minlength="3" maxlength="80" value="${esc(name)}" placeholder="${t('sg.namePh')}"></label>
      <label>${t('sg.area')}<input id="sgArea" required minlength="2" maxlength="80" list="sgAreas" placeholder="${t('sg.areaPh')}">
        <datalist id="sgAreas">${areas.map((a) => `<option value="${esc(a)}">`).join('')}</datalist></label>
      <label>${t('sg.landmark')}<input id="sgLandmark" maxlength="160" placeholder="${t('sg.landmarkPh')}"></label>
      <label>${t('sg.note')}<textarea id="sgNote" maxlength="240" rows="2" placeholder="${t('sg.notePh')}"></textarea></label>
      <label class="toggle"><input type="checkbox" id="sgHere"> <span>${t('sg.here')}</span></label>
      <button class="btn primary block" type="submit">${t('sg.send')}</button>
      <p class="fine">${t('sg.how')}</p>
    </form>`,
  (el) => {
    $('#sgForm', el).onsubmit = async (e) => {
      e.preventDefault();
      const b = e.target.querySelector('button[type=submit]'); b.disabled = true;
      let fix = null;
      if ($('#sgHere', el).checked) {
        b.textContent = t('sos.locating');
        try { fix = await getFix({ timeout: 12000, maximumAge: 30000 }); } catch { toast(t('loc.fail')); }
        b.textContent = t('sg.send');
      }
      try {
        const r = await community.rpc('suggest_pujo', {
          p_name: $('#sgName', el).value.trim(), p_area: $('#sgArea', el).value.trim(),
          p_landmark: $('#sgLandmark', el).value.trim() || null, p_note: $('#sgNote', el).value.trim() || null,
          p_lat: fix?.lat ?? null, p_lng: fix?.lng ?? null, p_accuracy: fix?.accuracy ?? null,
        });
        if (r.status === 'pending') {
          track('suggest_pujo', { d: fix ? 'with_location' : 'no_location' });
          toast(t('sg.thanks'), 5000);
          return closeSheet();
        }
        toast(t(['bad_name', 'bad_area', 'rate_limited'].includes(r.status) ? 'sg.err.' + r.status : 'sy.failed'));
      } catch { toast(t('sy.failed')); }
      b.disabled = false;
    };
  });
}

// Any [data-suggest] button anywhere in the app opens the form (with data-name to prefill a searched name).
document.addEventListener('click', (e) => {
  const b = e.target.closest('[data-suggest]');
  if (!b) return;
  e.preventDefault(); e.stopPropagation();
  suggestSheet({ name: b.dataset.name || '' });
});
