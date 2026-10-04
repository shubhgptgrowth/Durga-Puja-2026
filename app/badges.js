/* A badge's own page (tap one in My Pujo): the medallion, what it's for, and, once earned, a story card to
 * share. Locked badges show what it takes to get them. */
import { S, t, esc, fmt } from './state.js';
import { openSheet } from './ui.js';
import { BADGES, earned, daySteps } from './actions.js';
import { shareCard, appLink, myName } from './growth.js';

const nameOf = (b) => (S.prefs.lang === 'bn' ? b.bn : b.name);

/** 1080×1920 story card for a badge. */
export function badgeCard(b) {
  const visited = Object.keys(S.checkins).length;
  const steps = Object.values(S.history).reduce((a, r) => a + daySteps(r), 0);
  return {
    kicker: t('bd.cardKicker'), title: `${b.em} ${nameOf(b)}`, big: true,
    stats: [[fmt(visited), t('g.cardPandals')], [fmt(steps), t('g.cardSteps')]],
    lines: [t('b.' + b.id)],
    foot: myName() ? t('bd.cardFootName', { name: myName() }) : t('bd.cardFoot'),
  };
}

export function shareBadge(b) {
  const text = `${myName() ? t('bd.shareTextName', { name: myName(), badge: nameOf(b) }) : t('bd.shareText', { badge: nameOf(b) })}\n${appLink('ig_badge')}`;
  return shareCard(badgeCard(b), text, `pujo-badge-${b.id}.png`);
}

export function badgeSheet(id, { share = false } = {}) {
  const b = BADGES.find((x) => x.id === id); if (!b) return;
  const got = earned().has(id);
  if (share && got) return shareBadge(b);
  openSheet(`<div class="badge-pop ${got ? '' : 'locked'}">
      <div class="medal" aria-hidden="true"><span>${b.em}</span>${got ? '<i class="rays"></i>' : ''}</div>
      <p class="badge-eyebrow">${got ? t('bd.earned') : t('bd.locked')}</p>
      <h2>${esc(nameOf(b))}</h2>
      <p class="fine">${t('b.' + b.id)}</p>
      ${got ? `<div class="btn-row" style="justify-content:center;margin-top:14px"><button class="btn primary" id="bdShare">📸 ${t('bd.share')}</button></div>` : `<p class="fine" style="margin-top:10px">${t('bd.how')}</p>`}
    </div>`, (el) => { const s = el.querySelector('#bdShare'); if (s) s.onclick = () => shareBadge(b); });
}
