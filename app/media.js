/* Client-side media preparation for moments.
 * Photos are resized and re-encoded to JPEG. That keeps uploads around 200–400 KB on a
 * jammed network, and re-encoding through a canvas drops EXIF data, including GPS.
 * Every item also gets a small thumbnail, so the feed stays cheap to browse. */

export const FULL_PX = 1600, THUMB_PX = 480;

/** Scale (w, h) to fit inside `max` on the long edge, never upscaling. */
export function fitWithin(w, h, max) {
  const s = Math.min(1, max / Math.max(w, h));
  return [Math.max(1, Math.round(w * s)), Math.max(1, Math.round(h * s))];
}

const HEIC_NAME = /\.(heic|heif)$/i, VIDEO_NAME = /\.(mp4|m4v|mov|webm|3gp|3gpp|mkv)$/i;
const err = (code) => Object.assign(new Error(code), { code });

/** HEIC/HEIF, by type, name or the file's own header ("ftyp" + heic/heix/mif1/msf1...). Phone pickers often send no type. */
async function isHeic(file) {
  if (/image\/hei[cf]/i.test(file.type) || HEIC_NAME.test(file.name || '')) return true;
  if (file.type && !/octet-stream/.test(file.type)) return false;
  try {
    const b = new Uint8Array(await file.slice(0, 12).arrayBuffer());
    const tag = String.fromCharCode(...b.slice(4, 12));
    return tag.startsWith('ftyp') && /^(heic|heix|hevc|hevx|heim|heis|mif1|msf1|avif)/.test(tag.slice(4));
  } catch { return false; }
}

let heicLib = null;
/** The HEIC decoder (app/vendor/heic2any.min.js, about 1.3 MB) loads only the first time it is needed. */
function loadHeic() {
  return (heicLib ||= new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = new URL('vendor/heic2any.min.js', document.baseURI).href;
    s.onload = () => (window.heic2any ? res(window.heic2any) : rej(err('heic')));
    s.onerror = () => { heicLib = null; s.remove(); rej(err('heic')); };
    document.head.append(s);
  }));
}

async function decodeNative(file) {
  if ('createImageBitmap' in window) {
    try { return await createImageBitmap(file, { imageOrientation: 'from-image' }); } catch { /* try the next way */ }
    // Very large camera photos can run out of memory at full size: decode straight to a smaller size instead.
    try { return await createImageBitmap(file, { imageOrientation: 'from-image', resizeWidth: FULL_PX * 2, resizeQuality: 'high' }); } catch { /* next */ }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image(); img.decoding = 'async'; img.src = url; await img.decode();
    return img;
  } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
}

async function decode(file) {
  try { return await decodeNative(file); } catch { /* Safari opens HEIC itself; Chrome and most Android browsers do not */ }
  if (!(await isHeic(file))) throw err('unsupported');
  const heic2any = await loadHeic();
  let jpg;
  try { jpg = await heic2any({ blob: file, toType: 'image/jpeg', quality: 0.9 }); } catch { throw err('unsupported'); }
  return decodeNative(Array.isArray(jpg) ? jpg[0] : jpg);
}

function toJpeg(src, sw, sh, max, quality) {
  const [w, h] = fitWithin(sw, sh, max);
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const ctx = c.getContext('2d'); ctx.drawImage(src, 0, 0, w, h);
  return new Promise((res, rej) => c.toBlob((b) => (b ? res(b) : rej(new Error('encode failed'))), 'image/jpeg', quality));
}

export async function prepareImage(file) {
  const bmp = await decode(file);
  const sw = bmp.width || bmp.naturalWidth, sh = bmp.height || bmp.naturalHeight;
  const [full, thumb] = await Promise.all([toJpeg(bmp, sw, sh, FULL_PX, 0.82), toJpeg(bmp, sw, sh, THUMB_PX, 0.72)]);
  bmp.close?.();
  return { mediaType: 'image', full, thumb, ext: 'jpg', previewUrl: URL.createObjectURL(thumb) };
}

/** Videos are uploaded as recorded (within limits). The thumbnail is a frame taken about 0.5 s in. */
export async function prepareVideo(file, { maxSec = 30, maxMB = 20 } = {}) {
  if (file.size > maxMB * 1024 * 1024) throw Object.assign(new Error('too_big'), { code: 'too_big' });
  const url = URL.createObjectURL(file);
  const v = document.createElement('video');
  v.muted = true; v.playsInline = true; v.preload = 'auto'; v.src = url;
  try {
    await new Promise((res, rej) => { v.onloadedmetadata = res; v.onerror = () => rej(Object.assign(new Error('unsupported'), { code: 'unsupported' })); });
    if (v.duration > maxSec + 0.5) throw Object.assign(new Error('too_long'), { code: 'too_long' });
    v.currentTime = Math.min(0.5, (v.duration || 1) / 2);
    await new Promise((res) => { v.onseeked = res; setTimeout(res, 3000); });
    const thumb = await toJpeg(v, v.videoWidth || 640, v.videoHeight || 360, THUMB_PX, 0.72);
    const ext = ((file.type.split('/')[1] || (file.name || '').split('.').pop() || 'mp4').toLowerCase()).replace('quicktime', 'mov');
    return { mediaType: 'video', full: file, thumb, ext, duration: v.duration, previewUrl: URL.createObjectURL(thumb) };
  } finally { URL.revokeObjectURL(url); }
}

const isVideo = (f) => f.type.startsWith('video/') || (!f.type.startsWith('image/') && VIDEO_NAME.test(f.name || ''));
export const prepareMedia = (file, opts) => (isVideo(file) ? prepareVideo(file, opts) : prepareImage(file));
