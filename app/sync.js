/* My Pujo on every phone and browser: progress is backed up under a personal Pujo code (see
 * supabase/migrations/*_progress_sync.sql). On start, the backup is pulled and merged in; changes are pushed a
 * few seconds later and when the page is hidden. Another browser joins with the code or its link (#restore=…).
 * The phone number is never part of the backup. */
import { S, t, store, community } from './state.js';
import { mergeProgress } from './core.js';
import { rerender, toast } from './ui.js';

const LS = (k, d) => { try { const v = localStorage.getItem('pp:' + k); return v == null ? d : JSON.parse(v); } catch { return d; } };
let timer = null, ready = false, gen = 0, bootDone;
const booting = new Promise((r) => (bootDone = r)); // start-up pull and first save

function collect() {
  const p = S.prefs;
  return { v: 1, history: S.history, checkins: S.checkins, name: p.name || '', goal: p.goal, height: p.height, weight: p.weight,
    myMoments: store.get('myMoments', 0), myRatings: LS('community.myRatings', {}) };
}
function apply(m) {
  S.history = m.history; store.set('history', S.history);
  S.checkins = m.checkins; store.set('checkins', S.checkins);
  Object.assign(S.prefs, { name: m.name || S.prefs.name, goal: m.goal || S.prefs.goal, height: m.height || S.prefs.height, weight: m.weight || S.prefs.weight });
  store.set('prefs', S.prefs);
  store.set('myMoments', m.myMoments || 0);
  try { localStorage.setItem('pp:community.myRatings', JSON.stringify(m.myRatings || {})); } catch { /* private mode */ }
}
const hasProgress = (d) => Object.keys(d.checkins || {}).length || Object.values(d.history || {}).some((r) => (r.steps || r.m || (r.pandals || []).length));

export const pujoCode = () => store.get('pujoCode', null);
export const restoreLink = (code = pujoCode()) => `${location.origin}${location.pathname}#restore=${code}`;

export async function saveNow() {
  if (!community.enabled || !ready) return;
  clearTimeout(timer); timer = null;
  const data = collect(), g = gen;
  if (!pujoCode() && !hasProgress(data)) return; // nothing worth a backup yet
  try {
    const r = await community.rpc('save_progress', { p_data: data });
    if (g === gen && r?.code && r.code !== pujoCode()) { store.set('pujoCode', r.code); if (S.view === 'me') rerender(); } // the first backup: show its code
  } catch { /* offline: next change retries */ }
}
const later = () => { if (!ready) return; clearTimeout(timer); timer = setTimeout(saveNow, 8000); };

/** Pull the backup, merge it in, push the merge. Called once at start-up (after a Google sign-in return, if any). */
export async function startSync(authP = null) {
  if (!community.enabled) return;
  document.addEventListener('pp:dirty', later);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden' && timer) saveNow(); });
  const a = await authP;
  if (a?.status === 'redirecting') return; // on to Google again
  if (a?.status === 'ok') toast(t('gs.welcome', { email: a.email || '' }), 4500);
  if (a?.status === 'error') toast(t('gs.failed'), 4500);
  return boot(a?.status === 'ok').finally(bootDone);
}
async function boot(signedIn = false) {
  try {
    let r = await community.rpc('load_progress', {});
    // First sign-in with this Google account from a browser that already had a backup: keep that backup.
    if (!r?.code && signedIn && pujoCode()) {
      const c = await community.rpc('claim_progress', { p_code: pujoCode() });
      if (c?.status === 'ok') r = c;
    }
    if (r?.code) {
      store.set('pujoCode', r.code);
      const merged = mergeProgress(collect(), r.data || {});
      apply(merged);
    }
    if (signedIn || r?.code) rerender();
  } catch { /* offline: work locally */ }
  ready = true;
  await saveNow();
}

/** Join this browser to another device's backup (a typed code or a #restore= link). */
export async function claimCode(code) {
  if (!community.enabled) return toast(t('sy.off'));
  await booting; // let the start-up pull and first save finish, so they can't answer with the old code
  try {
    const r = await community.rpc('claim_progress', { p_code: code });
    if (r.status !== 'ok') return toast(t(r.status === 'rate_limited' ? 'sy.slow' : 'sy.notFound'), 3500);
    gen++; store.set('pujoCode', r.code);
    apply(mergeProgress(collect(), r.data || {}));
    ready = true; await saveNow(); rerender();
    toast(t('sy.restored'), 4000);
  } catch { toast(t('sy.failed')); }
}

/** Sign out of Google here: saves first, then this browser forgets the pujo (it stays in the Google account). */
export async function signOutHere() {
  await saveNow();
  await community.signOut();
  for (const k of ['history', 'checkins', 'pujoCode', 'myMoments', 'community.myRatings', 'walking']) { try { localStorage.removeItem('pp:' + k); } catch { /* ignore */ } }
  Object.assign(S.prefs, { name: '', phone: '', contactOk: false }); store.set('prefs', S.prefs);
  location.replace(location.pathname + '#me'); location.reload();
}
