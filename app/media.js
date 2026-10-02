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

async function decode(file) {
  if ('createImageBitmap' in window) {
    try { return await createImageBitmap(file, { imageOrientation: 'from-image' }); } catch { /* fall through */ }
  }
  const url = URL.createObjectURL(file);
  try {
    const img = new Image(); img.decoding = 'async'; img.src = url; await img.decode();
    return img;
  } finally { setTimeout(() => URL.revokeObjectURL(url), 1000); }
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
    const ext = (file.type.split('/')[1] || 'mp4').replace('quicktime', 'mov');
    return { mediaType: 'video', full: file, thumb, ext, duration: v.duration, previewUrl: URL.createObjectURL(thumb) };
  } finally { URL.revokeObjectURL(url); }
}

export const prepareMedia = (file, opts) => (file.type.startsWith('video/') ? prepareVideo(file, opts) : prepareImage(file));
