/* Real photos for tiles and list rows: Wikimedia Commons photos already in the guide (credited on place pages
 * and in Moments), plus a few saved tile photos in img/tiles (credits in img/tiles/tiles.json). Commons
 * thumbnails come in fixed widths, so the URL's width is swapped for a smaller standard one.
 * Low-data mode turns them all off. */
import { S, G, idx, esc } from './state.js';

export const photosOn = () => !S.prefs.lowData;
export const px = (src, w) => (src ? src.replace(/\/\d+px-/, `/${w}px-`) : '');
export const pandalPhoto = (id, w = 330) => px(idx.pandal[id]?.photos?.[0]?.src, w);
export function dishPhoto(names, w = 330) {
  const dp = G.data.dish_photos || {};
  const k = names.find((n) => dp[n]);
  return k ? px(dp[k].src, w) : '';
}
// What a place of each kind typically serves, for eateries with no photo of their own or of their dishes.
const BY_TYPE = {
  sweets: ['Rosogolla', 'Mishti', 'Sandesh', 'Nolen gur sandesh'], street: ['Phuchka', 'Kathi roll', 'Egg roll', 'Rolls'],
  restaurant: ['Biryani', 'Mutton biryani', 'Kosha mangsho', 'Bengali thali'], drinks: ['Daab sherbet', 'Desserts', 'Ice cream'],
  cabin: ['Fish kabiraji', 'Fish fry', 'Mutton cutlet', 'Moghlai paratha'],
};
export function foodPhoto(f, w = 250) {
  if (!photosOn()) return '';
  return px(f.photos?.[0]?.src, w) || dishPhoto(f.dishes, w) || dishPhoto(BY_TYPE[f.type] || BY_TYPE.restaurant, w);
}
/** Best photo for a set of areas: their most famous pandal's, else a saved tile photo. */
export function areaPhoto(zoneIds, fallbackKey, w = 500) {
  if (!photosOn()) return '';
  const best = zoneIds.flatMap((id) => idx.zone[id]?.pandal_ids || []).map((id) => idx.pandal[id])
    .filter((p) => p?.photos?.length).sort((a, b) => b.popularity - a.popularity)[0];
  return best ? px(best.photos[0].src, w) : fallbackKey ? `img/tiles/${fallbackKey}.jpg` : '';
}
export const tilePhoto = (key) => (photosOn() ? `img/tiles/${key}.jpg` : '');
/** A full-bleed background photo for a tile; one that fails to load is dropped, leaving the tile's colour. */
export const photoBg = (src, cls = 'tile-img') => (src ? `<img class="${cls}" src="${esc(src)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">` : '');
