"""The punch look ("style": "punch", from 3 Nov 2026): fast, bold reels that hold attention.

What changes from the cinematic look (build2.py):
- Shots of 1.4 to 2.2 s, full-bleed 9:16 at 30 fps, each with a quick punch-in zoom (ease-out over 0.3 s, then a
  slow drift), alternating in and out, and a three-frame white flash on every cut.
- Big condensed type (Anton, upper case) with a soft dark band behind it; words in [brackets] sit in a saffron box.
- The hook is on screen, full size, from the very first frame (it is also the cover), every later line pops in
  (scale 0.7 to 1 with a small overshoot).
- A thin saffron progress bar across the top fills as the reel plays.
- No black end card: the last shot carries the question, darkened, with the guide address and the credits small
  under it, so the reel loops straight back into the hook.

Plan fields: hook (plain, for the manifest), hook_text (the hook with [highlights]), segments [[clip, start_s, secs, "Line with [highlight]", cx?, cy?], ...], end [question, sub],
end_clip [clip, start_s, cx?, cy?] (defaults to the last shot running on), end_secs (2.8), music [clip, start_s].
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from . import build2 as b2

W, H, FPS = b2.W, b2.H, 30
OVER = 1.3  # sources are prepared 30% larger than the frame so the camera can push in without upscaling
SAFFRON, INK, WHITE = (255, 186, 28), (24, 14, 10), (255, 255, 255)
HOOK_Y, LINE_Y, TEXT_W = 640, 1010, 880  # centres of the hook and of the lines; clear of Instagram's own overlays
BAR_Y = 206


def face(name, size):
    for n in (name, "Poppins-ExtraBold.ttf"):
        try:
            return ImageFont.truetype(os.path.join(b2.FONTS, n), size)
        except OSError:
            continue
    return ImageFont.load_default()


def ease_out(u):
    return 1 - (1 - u) ** 3


def ease_back(u, k=1.6):
    u -= 1
    return 1 + (k + 1) * u ** 3 + k * u ** 2


def tokens(text):
    """Words to set, as units that never break: a [bracketed run] is one saffron box even when it has spaces in it,
    and punctuation written against it stays on it. 'Kali Puja on [Sun 8 Nov]. Why?' ->
    [[('KALI', 0)], [('PUJA', 0)], [('ON', 0)], [('SUN 8 NOV', 1), ('.', 0)], [('WHY?', 0)]]."""
    units, cur, buf, hi = [], [], "", False

    def flush(as_hi):
        nonlocal buf
        if buf:
            cur.append((buf.upper(), as_hi))
        buf = ""

    for ch in text:
        if ch == "[":
            flush(False)
            hi = True
        elif ch == "]":
            flush(True)
            hi = False
        elif ch.isspace() and not hi:
            flush(False)
            if cur:
                units.append(cur)
                cur = []
        else:
            buf += ch
    flush(hi)
    if cur:
        units.append(cur)
    return units


BOX = 18  # padding each side of a saffron box


def text_block(text, size, maxw=TEXT_W, font="Anton-Regular.ttf"):
    """The words set in lines no wider than maxw, highlighted runs on a saffron box: a tight RGBA image."""
    while True:
        f = face(font, size)
        sp = f.getlength(" ")
        lines, cur, cw = [], [], 0
        for unit in tokens(text):
            uw = sum(f.getlength(t) + (2 * BOX if hi else 0) for t, hi in unit)
            if cur and cw + sp + uw > maxw:
                lines.append(cur)
                cur, cw = [], 0
            cur.append((unit, uw))
            cw += (sp if cw else 0) + uw
        if cur:
            lines.append(cur)
        if (len(lines) <= 3 and all(sum(w for _, w in ln) + sp * (len(ln) - 1) <= maxw for ln in lines)) or size <= 60:
            break
        size -= 8
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * 1.08)
    pad = 30
    im = Image.new("RGBA", (maxw + 2 * pad, lh * len(lines) + 2 * pad), (0, 0, 0, 0))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d, sd = ImageDraw.Draw(im), ImageDraw.Draw(sh)
    stroke = max(3, size // 18)
    for li, ln in enumerate(lines):
        tw = sum(w for _, w in ln) + sp * (len(ln) - 1)
        x, y = pad + (maxw - tw) / 2, pad + li * lh
        for unit, uw in ln:
            for t, hi in unit:
                tw_ = f.getlength(t)
                if hi:
                    d.rounded_rectangle((x, y + lh * 0.04, x + tw_ + 2 * BOX, y + lh * 0.98), radius=14, fill=SAFFRON)
                    d.text((x + BOX, y), t, font=f, fill=INK)
                    x += tw_ + 2 * BOX
                else:
                    sd.text((x + 3, y + 5), t, font=f, fill=(0, 0, 0, 230))
                    d.text((x, y), t, font=f, fill=WHITE, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))
                    x += tw_
            x += sp
    out = Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(7)), im)
    return out.crop(out.getbbox() or (0, 0, 1, 1))


def band(cy, half, peak):
    """A soft dark band centred on cy so white type reads on any picture."""
    g = Image.new("L", (1, H), 0)
    for y in range(H):
        u = max(0.0, 1 - abs(y - cy) / half)
        g.putpixel((0, y), int(peak * (u ** 0.8)))
    return Image.merge("RGBA", (Image.new("L", (1, H), 0),) * 3 + (g,)).resize((W, H))


def prepare_still(path, cx, cy):
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    bw, bh = int(W * OVER), int(H * OVER)
    k = max(bw / im.width, bh / im.height)
    im = im.resize((max(bw, round(im.width * k)), max(bh, round(im.height * k))), Image.LANCZOS)
    x = min(max(0, round(im.width * cx - bw / 2)), im.width - bw)
    y = min(max(0, round(im.height * cy - bh / 2)), im.height - bh)
    im = im.crop((x, y, x + bw, y + bh))
    return ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.08)).enhance(1.15)


def video_frames(path, start, secs, cx, cy):
    """Frames of a clip, cut OVER x the frame around (cx, cy), graded; the last frame holds if the clip runs short."""
    bw, bh = int(W * OVER) // 2 * 2, int(H * OVER) // 2 * 2
    n = round(secs * FPS)
    vf = (f"scale={bw}:{bh}:force_original_aspect_ratio=increase:flags=bicubic,"
          f"crop={bw}:{bh}:'max(0,min(iw-{bw},iw*{cx}-{bw}/2))':'max(0,min(ih-{bh},ih*{cy}-{bh}/2))',"
          f"fps={FPS},eq=contrast=1.08:saturation=1.15")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(start), "-t", f"{secs + 0.5:.2f}", "-i", path, "-an",
                          "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    last, size = None, bw * bh * 3
    for _ in range(n):
        buf = p.stdout.read(size)
        if len(buf) == size:
            last = Image.frombytes("RGB", (bw, bh), buf)
        if last is None:
            raise SystemExit(f"no frames from {path}")
        yield last
    p.stdout.close()
    p.wait()


def camera(img, u, t, i):
    """The punch: a quick push (or pull on alternate shots) over the first 0.3 s, then a slow drift."""
    q = ease_out(min(1.0, t / 0.3))
    z = (1.0 + 0.12 * q + 0.05 * u) if i % 2 == 0 else (1.24 - 0.12 * q - 0.04 * u)
    z = min(max(z, 1.0), OVER)
    cw, ch = img.width / z, img.height / z
    dx = (1 if i % 3 else -1) * (img.width - cw) * 0.25 * (u - 0.5)
    x0, y0 = (img.width - cw) / 2 + dx, (img.height - ch) / 2
    s = cw / W
    return img.transform((W, H), Image.AFFINE, (s, 0, x0, 0, s, y0), resample=Image.BILINEAR)


def end_layer(question, sub, credits):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    q = text_block(question, 104)
    im.alpha_composite(q, ((W - q.width) // 2, 760 - q.height // 2))
    d = ImageDraw.Draw(im)
    y = 760 + q.height // 2 + 30
    if sub:
        f = face("Poppins-ExtraBold.ttf", 40)
        t = sub.upper()
        d.text(((W - d.textlength(t, font=f)) / 2, y), t, font=f, fill=SAFFRON)
        y += 76
    f = face("Poppins-SemiBold.ttf", 34)
    t = "Free festival guide: pujoparikramaguide.in"
    d.text(((W - d.textlength(t, font=f)) / 2, y + 20), t, font=f, fill=WHITE)
    fc, yy = face("Poppins-SemiBold.ttf", 20), 1330
    for ln in b2.wrap(d, credits, fc, W - 200)[:6]:
        d.text(((W - d.textlength(ln, font=fc)) / 2, yy), ln, font=fc, fill=(205, 195, 180))
        yy += 27
    return im


def build(reel, footage, src_dir, out_dir, tmp):
    segs = [list(s) for s in reel["segments"]]
    end_secs = reel.get("end_secs", 2.8) if reel.get("end") else 0
    if end_secs:
        last = segs[-1]
        ec = reel.get("end_clip") or [last[0], last[1] + last[2], *last[4:]]
        segs.append([ec[0], ec[1], end_secs, None, *ec[2:]])
    total = sum(s[2] for s in segs)
    nframes = round(total * FPS)
    vid = f"{tmp}/{reel['id']}_punch.mp4"
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                            "-pix_fmt", "yuv420p", vid], stdin=subprocess.PIPE)
    hook_band, line_band = band(HOOK_Y, 420, 150), band(LINE_Y, 300, 140)
    dim = Image.new("RGBA", (W, H), (0, 0, 0, 120))
    endl = None
    if end_secs:  # the credits name the closing shot too
        endl = end_layer(reel["end"][0], reel["end"][1] if len(reel["end"]) > 1 else "",
                         b2.credits_for(dict(reel, segments=segs), footage))
    k = 0
    for i, (sid, start, secs, text, *rest) in enumerate(segs):
        cx = rest[0] if rest else 0.5
        cy = rest[1] if len(rest) > 1 else 0.45
        path = b2.src_file(src_dir, sid)
        is_end = text is None and end_secs and i == len(segs) - 1
        hook = i == 0 and reel.get("hook")
        label = text_block(reel.get("hook_text") or reel["hook"], 128) if hook else (text_block(text, 96) if text else None)
        n = round(secs * FPS)
        if path.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            base = prepare_still(path, cx, cy)
            frames = (base for _ in range(n))
        else:
            frames = video_frames(path, start, secs, cx, cy)
        for j, src in enumerate(frames):
            t, u = j / FPS, j / max(1, n - 1)
            fr = camera(src, u, t, i).convert("RGBA")
            if is_end:
                fr.alpha_composite(dim)
                a = min(1.0, t / 0.18)
                lay = endl if a >= 1 else Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 0)), endl, a)
                fr.alpha_composite(lay)
            elif label is not None:
                fr.alpha_composite(hook_band if hook else line_band)
                if hook:
                    s, a = 1.0 + 0.05 * (1 - ease_out(min(1.0, t / 0.4))), 1.0
                else:
                    s, a = 0.7 + 0.3 * ease_back(min(1.0, t / 0.24)), min(1.0, t / 0.08)
                lw, lh = max(1, int(label.width * s)), max(1, int(label.height * s))
                lab = label.resize((lw, lh), Image.BILINEAR) if s != 1 else label
                if a < 1:
                    lab = lab.copy()
                    lab.putalpha(lab.getchannel("A").point(lambda v: int(v * a)))
                cy_ = HOOK_Y if hook else LINE_Y
                fr.alpha_composite(lab, ((W - lw) // 2, cy_ - lh // 2))
            if i > 0 and j < 3:  # the flash on the cut
                fr = Image.blend(fr, Image.new("RGBA", (W, H), (255, 255, 255, 255)), (0.55, 0.25, 0.08)[j])
            d = ImageDraw.Draw(fr)
            d.rounded_rectangle((60, BAR_Y, W - 60, BAR_Y + 7), radius=4, fill=(255, 255, 255, 70))
            d.rounded_rectangle((60, BAR_Y, 60 + max(8, (W - 120) * (k + 1) / nframes), BAR_Y + 7), radius=4, fill=SAFFRON)
            enc.stdin.write(fr.convert("RGB").tobytes())
            k += 1
    enc.stdin.close()
    if enc.wait():
        raise SystemExit("ffmpeg failed encoding the punch reel")
    out = f"{out_dir}/{reel['id']}.mp4"
    m = reel.get("music")
    if m:
        audio = ["-ss", str(m[1]), "-t", f"{total:.2f}", "-i", b2.src_file(src_dir, m[0])]
        af = (f"[1:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.15,"
              f"afade=t=out:st={max(0.0, total - 0.8):.2f}:d=0.8,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    else:
        audio = ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=48000:cl=stereo"]
        af = "[1:a]anull[aout]"
    b2.run("ffmpeg", "-y", "-i", vid, *audio, "-filter_complex", af, "-map", "0:v", "-map", "[aout]", "-t", f"{total:.2f}",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-profile:v", "high", "-pix_fmt", "yuv420p",
           "-maxrate", "14M", "-bufsize", "28M", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-movflags", "+faststart", out)
    b2.write_caption(reel, footage, out_dir)
    return total
