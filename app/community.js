/* Community layer: shared check-in / "ate here" counts and location-tagged moments.
 * Talks to Supabase over its plain REST APIs (Auth, PostgREST, Storage) with no SDK.
 * The schema and the server-side rules live in supabase/migrations.
 *
 * Built for bad pandal-side networks:
 * - Visits are queued in localStorage with the GPS fix and time captured at the moment,
 *   then flushed when the network returns. The server accepts them up to 12 h late.
 * - Moments are queued in IndexedDB (the media blobs included) and uploaded later.
 * - Place stats are cached, so counts still render offline. */

const LS = 'pp:';
const lsGet = (k, d) => { try { const v = localStorage.getItem(LS + k); return v == null ? d : JSON.parse(v); } catch { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem(LS + k, JSON.stringify(v)); } catch { /* quota or private mode */ } };

export class Community {
  constructor(cfg = {}) {
    this.url = (cfg.url || '').replace(/\/+$/, '');
    this.key = cfg.anonKey || '';
    this.bucket = cfg.bucket || 'moments';
    this.enabled = Boolean(this.url && this.key);
    this.session = lsGet('sb.session', null);
    this.stats = lsGet('community.stats', { at: 0, byPlace: {} });
    this.listeners = new Set();
    this.flushing = false;
  }

  on(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); }
  emit(type, detail) { for (const fn of this.listeners) { try { fn(type, detail); } catch { /* listener bug */ } } }

  /* ------------------------------------------------------------ auth (anonymous) */
  get userId() { return this.session?.user?.id || null; }

  async ensureSession() {
    if (!this.enabled) throw new Error('community disabled');
    const s = this.session, now = Date.now() / 1000;
    if (s?.access_token && s.expires_at - now > 60) return s;
    if (s?.refresh_token) {
      try { return this._saveSession(await this._auth('token?grant_type=refresh_token', { refresh_token: s.refresh_token })); }
      catch (e) { if (e.status !== 400 && e.status !== 401 && e.status !== 403) throw e; }
    }
    return this._saveSession(await this._auth('signup', { data: {} })); // anonymous sign-in
  }
  _saveSession(r) {
    const expires_at = r.expires_at || Math.floor(Date.now() / 1000) + (r.expires_in || 3600);
    this.session = { access_token: r.access_token, refresh_token: r.refresh_token, expires_at, user: { id: r.user?.id } };
    lsSet('sb.session', this.session);
    return this.session;
  }
  async _auth(path, body) {
    const res = await fetch(`${this.url}/auth/v1/${path}`, {
      method: 'POST', headers: { apikey: this.key, 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    if (!res.ok) throw Object.assign(new Error(`auth ${res.status}`), { status: res.status });
    return res.json();
  }

  _headers(withUser) {
    const h = { apikey: this.key, 'Content-Type': 'application/json' };
    if (withUser && this.session?.access_token) h.Authorization = `Bearer ${this.session.access_token}`;
    return h;
  }

  async rpc(fn, args, retry = true) {
    await this.ensureSession();
    const res = await fetch(`${this.url}/rest/v1/rpc/${fn}`, { method: 'POST', headers: this._headers(true), body: JSON.stringify(args) });
    if (res.status === 401 && retry) { this.session = { ...this.session, expires_at: 0 }; return this.rpc(fn, args, false); }
    if (!res.ok) throw Object.assign(new Error(`${fn} ${res.status}`), { status: res.status });
    return res.json();
  }

  /* ------------------------------------------------------------ reach (no sign-in) */
  async trackOpen(device, src, firstSrc) {
    if (!this.enabled) return null;
    const res = await fetch(`${this.url}/rest/v1/rpc/track_open`, { method: 'POST', headers: this._headers(false),
      body: JSON.stringify({ p_device: device, p_src: src, p_first_src: firstSrc }) });
    if (!res.ok) throw new Error(`track_open ${res.status}`);
    return res.json();
  }

  /* ------------------------------------------------------------ place stats */
  async refreshStats() {
    if (!this.enabled) return this.stats;
    const res = await fetch(`${this.url}/rest/v1/place_stats?select=place_id,visits,today,last_hour,photos`, { headers: this._headers(false) });
    if (!res.ok) throw new Error(`stats ${res.status}`);
    const byPlace = {};
    for (const r of await res.json()) byPlace[r.place_id] = r;
    this.stats = { at: Date.now(), byPlace };
    lsSet('community.stats', this.stats);
    this.emit('stats', this.stats);
    return this.stats;
  }
  statFor(id) { return this.stats.byPlace[id] || null; }
  bump(id, patch) {
    const cur = this.stats.byPlace[id] || { place_id: id, visits: 0, today: 0, last_hour: 0, photos: 0 };
    this.stats.byPlace[id] = { ...cur, ...patch };
    lsSet('community.stats', this.stats);
    this.emit('stats', this.stats);
  }

  /* ------------------------------------------------------------ visits */
  get pendingVisits() { return lsGet('community.visitQueue', []); }

  /** Queue a verified visit and try to send it. Resolves to the server result, or {status:'queued'}. */
  async recordVisit(placeId, fix) {
    const item = { placeId, lat: fix.lat, lng: fix.lng, acc: fix.accuracy ?? null, at: new Date(fix.t || Date.now()).toISOString() };
    const q = this.pendingVisits.filter((x) => !(x.placeId === placeId && x.at.slice(0, 10) === item.at.slice(0, 10)));
    q.push(item); lsSet('community.visitQueue', q);
    const results = await this.flushVisits();
    return results.find((r) => r.placeId === placeId)?.result || { status: 'queued' };
  }

  async flushVisits() {
    if (!this.enabled || this.flushing) return [];
    this.flushing = true;
    const out = [];
    try {
      let q = this.pendingVisits;
      while (q.length) {
        const v = q[0];
        let result;
        try {
          result = await this.rpc('record_visit', { p_place: v.placeId, p_lat: v.lat, p_lng: v.lng, p_accuracy: v.acc, p_at: v.at });
        } catch (e) {
          if (e.status && e.status < 500 && e.status !== 429) result = { status: 'error' }; // permanent: drop it
          else break; // offline or server trouble: keep it for later
        }
        out.push({ placeId: v.placeId, result });
        if (result.status === 'counted' || result.status === 'duplicate') this.bump(v.placeId, { today: result.today, visits: result.visits });
        q = this.pendingVisits.slice(1); lsSet('community.visitQueue', q);
      }
    } finally { this.flushing = false; }
    if (out.length) this.emit('visits', out);
    return out;
  }

  /* ------------------------------------------------------------ moments */
  mediaUrl(path) { return `${this.url}/storage/v1/object/public/${this.bucket}/${path.split('/').map(encodeURIComponent).join('/')}`; }

  async feed({ placeIds = null, onSiteOnly = false, before = null, limit = 30 } = {}) {
    if (!this.enabled) return [];
    if (this.session) { try { await this.ensureSession(); } catch { /* read anonymously */ } }
    const p = new URLSearchParams({ select: '*', order: 'created_at.desc', limit: String(limit) });
    if (placeIds?.length === 1) p.set('place_id', `eq.${placeIds[0]}`);
    else if (placeIds?.length) p.set('place_id', `in.(${placeIds.join(',')})`);
    if (onSiteOnly) p.set('on_site', 'is.true');
    if (before) p.set('created_at', `lt.${before}`);
    const res = await fetch(`${this.url}/rest/v1/photos_feed?${p}`, { headers: this._headers(true) });
    if (!res.ok) throw new Error(`feed ${res.status}`);
    return res.json();
  }

  upload(path, blob, contentType, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${this.url}/storage/v1/object/${this.bucket}/${path}`);
      xhr.setRequestHeader('apikey', this.key);
      xhr.setRequestHeader('Authorization', `Bearer ${this.session.access_token}`);
      xhr.setRequestHeader('Content-Type', contentType);
      xhr.setRequestHeader('x-upsert', 'false');
      xhr.setRequestHeader('cache-control', 'max-age=31536000');
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
      xhr.onload = () => (xhr.status < 300 ? resolve() : reject(Object.assign(new Error(`upload ${xhr.status}`), { status: xhr.status })));
      xhr.onerror = () => reject(Object.assign(new Error('network'), { status: 0 }));
      xhr.send(blob);
    });
  }

  /** item: {placeId, mediaType, full:Blob, thumb:Blob, ext, caption, fix:{lat,lng,accuracy}} */
  async publishMoment(item, onProgress) {
    const s = await this.ensureSession();
    const stamp = new Date().toISOString().slice(0, 10);
    const rand = (crypto.randomUUID?.() || Math.random().toString(36).slice(2)).replace(/-/g, '').slice(0, 16);
    const path = `${s.user.id}/${stamp}/${rand}.${item.ext}`, thumbPath = `${s.user.id}/${stamp}/${rand}_t.jpg`;
    const fullType = item.full.type || (item.mediaType === 'video' ? 'video/mp4' : 'image/jpeg');
    await this.upload(path, item.full, fullType, (p) => onProgress?.(p * 0.85));
    await this.upload(thumbPath, item.thumb, 'image/jpeg', (p) => onProgress?.(0.85 + p * 0.1));
    const r = await this.rpc('add_photo', {
      p_place: item.placeId, p_path: path, p_thumb_path: thumbPath, p_media_type: item.mediaType,
      p_caption: item.caption || null, p_lat: item.fix?.lat ?? null, p_lng: item.fix?.lng ?? null, p_accuracy: item.fix?.accuracy ?? null,
    });
    onProgress?.(1);
    if (r.status === 'ok') { this.bump(item.placeId, { photos: (this.statFor(item.placeId)?.photos || 0) + 1 }); this.emit('moment', r); }
    return r;
  }

  /** Publish now, or keep the moment in IndexedDB and retry when back online. */
  async addMoment(item, onProgress) {
    try {
      return await this.publishMoment(item, onProgress);
    } catch (e) {
      if (e.status && e.status !== 0 && e.status < 500 && e.status !== 429) throw e;
      await idbPut({ ...item, id: Date.now() + Math.random(), queuedAt: Date.now() });
      return { status: 'queued' };
    }
  }
  async pendingMoments() { return idbAll(); }
  async flushMoments() {
    if (!this.enabled || !navigator.onLine) return 0;
    let n = 0;
    for (const item of await idbAll()) {
      try {
        const r = await this.publishMoment(item);
        await idbDelete(item.id);
        if (r.status === 'ok') n++;
      } catch (e) {
        if (e.status && e.status < 500 && e.status !== 429) await idbDelete(item.id); // rejected for good
        else break;
      }
    }
    if (n) this.emit('flushed', n);
    return n;
  }

  toggleLike(id) { return this.rpc('toggle_like', { p_photo: id }); }
  report(id, reason) { return this.rpc('report_photo', { p_photo: id, p_reason: reason }); }
  async deleteMoment(id) {
    const r = await this.rpc('delete_photo', { p_photo: id });
    if (r.status === 'ok') {
      await fetch(`${this.url}/storage/v1/object/${this.bucket}`, {
        method: 'DELETE', headers: this._headers(true), body: JSON.stringify({ prefixes: [r.path, r.thumb_path] }),
      }).catch(() => {});
    }
    return r;
  }

  /** Flush both queues: call on boot, on 'online', and on visibility change. */
  async sync() {
    if (!this.enabled || !navigator.onLine) return;
    await this.flushVisits().catch(() => {});
    await this.flushMoments().catch(() => {});
    await this.refreshStats().catch(() => {});
  }
}

/* ------------------------------------------------------------ tiny IndexedDB queue */
const DB = 'pp-community', STORE = 'pendingMoments';
function idb() {
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: 'id' });
    r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error);
  });
}
async function tx(mode, fn) {
  const db = await idb();
  return new Promise((res, rej) => {
    const t = db.transaction(STORE, mode), st = t.objectStore(STORE), out = fn(st);
    t.oncomplete = () => res(out?.result ?? out); t.onerror = () => rej(t.error);
  });
}
const idbPut = (v) => tx('readwrite', (s) => s.put(v)).catch(() => {});
const idbDelete = (k) => tx('readwrite', (s) => s.delete(k)).catch(() => {});
const idbAll = () => tx('readonly', (s) => s.getAll()).catch(() => []);
