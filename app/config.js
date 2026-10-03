/* Deployment configuration. Everything here is public by design:
 * - The Supabase anon (or "publishable") key is meant to ship in browsers. Row-level
 *   security and the RPCs in supabase/migrations decide what it can do.
 * - Leave community.url empty to run without community features. The app then
 *   works fully offline-first, but without shared counts or moments.
 */
export const CONFIG = {
  community: {
    url: 'https://wmvzakyqnwfekyhjkprp.supabase.co',
    anonKey: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Indtdnpha3lxbndmZWt5aGprcHJwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTA5MjY2NjcsImV4cCI6MjEwNjUwMjY2N30.Y-ipJgHiPYhpKvi91q1Im028HsHPQKpi-DJaYhrULRA',  // public by design; RLS + RPCs enforce the rules
    bucket: 'moments',
    statsRefreshSec: 180,  // each poll is ~12 KB; keep egress inside the plan during the marketing push
    maxVideoSec: 30,
    maxVideoMB: 20,
  },
  map: {
    // Raster tile templates. Swap these for a keyed provider before a big launch (see docs/product/MAPS.md).
    light: 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
    dark: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    subdomains: 'abcd',
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
};

// Test and preview override: a page can set window.PP_CONFIG before the app loads.
if (typeof window !== 'undefined' && window.PP_CONFIG) {
  for (const [k, v] of Object.entries(window.PP_CONFIG)) CONFIG[k] = { ...CONFIG[k], ...v };
}
