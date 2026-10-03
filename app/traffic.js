/* Road closures and traffic advisories during the pujo. Kolkata Traffic Police loads its puja one-ways,
 * diversions and closures into Google Maps, and every Directions button here opens Google Maps,
 * so routes follow them. Official notices are listed from app/data/traffic.json, which the team curates. */
import { t, esc } from './state.js';

let data = null;
export function loadTraffic(onReady) {
  if (data) return data;
  fetch('data/traffic.json').then((r) => r.json()).then((d) => { data = d; onReady?.(); }).catch(() => { data = { notices: [] }; });
  return null;
}
export function trafficHtml() {
  const notices = (data?.notices || []).slice(0, 3);
  return `<div class="notice traffic"><b>🚧 ${t('tr2.title')}</b>
    <span>${t('tr2.body')}</span>
    ${notices.map((n) => `<a href="${esc(n.url)}" target="_blank" rel="noopener">${esc(n.title)}${n.date ? ` · ${esc(n.date)}` : ''}</a>`).join('')}
    <span class="fine">${t('tr2.help', { link: '<a href="https://kolkatatrafficpolice.gov.in/" target="_blank" rel="noopener">kolkatatrafficpolice.gov.in</a>' })}</span></div>`;
}
