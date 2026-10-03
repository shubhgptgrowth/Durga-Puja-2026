/* Road closures and traffic advisories during the pujo. Every Directions button opens Google Maps, where
 * Kolkata Traffic Police has published puja diversions in past years. Official notices come from two places:
 * - public.traffic_notices, filled every 3 hours by the `traffic-fetch` Edge Function running in Mumbai
 *   (the police site doesn't answer from outside India), and
 * - app/data/traffic.json, for notices the team adds by hand (newest first). */
import { t, esc } from './state.js';
import { CONFIG } from './config.js';

let data = null, loading = false;
export function loadTraffic(onReady) {
  if (data || loading) return data;
  loading = true;
  const c = CONFIG.community;
  const live = c?.url
    ? fetch(`${c.url}/rest/v1/traffic_notices?select=title,url,first_seen&order=first_seen.desc&limit=6`, { headers: { apikey: c.anonKey } })
      .then((r) => (r.ok ? r.json() : [])).catch(() => [])
    : Promise.resolve([]);
  const curated = fetch('data/traffic.json').then((r) => r.json()).then((d) => d.notices || []).catch(() => []);
  Promise.all([curated, live]).then(([a, b]) => {
    const seen = new Set(), notices = [];
    for (const n of [...a, ...b.map((x) => ({ title: x.title, url: x.url, date: (x.first_seen || '').slice(0, 10) }))]) {
      if (!n.url || seen.has(n.url)) continue; seen.add(n.url); notices.push(n);
    }
    data = { notices }; loading = false; onReady?.();
  });
  return null;
}
export function trafficHtml() {
  const notices = (data?.notices || []).slice(0, 3);
  return `<div class="notice traffic"><b>🚧 ${t('tr2.title')}</b>
    <span>${t('tr2.body')}</span>
    ${notices.map((n) => `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}${n.date ? ` · ${esc(n.date)}` : ''}</a>`).join('')}
    <span class="fine">${t('tr2.help', { link: '<a href="https://kolkatatrafficpolice.gov.in/" target="_blank" rel="noopener">kolkatatrafficpolice.gov.in</a>' })}</span></div>`;
}
