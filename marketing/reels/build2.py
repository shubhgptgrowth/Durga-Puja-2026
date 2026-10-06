"""Build Instagram Reels from real CC-licensed footage (Wikimedia Commons) plus a few AI shots, with music and credits.

    python3 build2.py spec2.json footage.json src_dir out_dir [reel_id,...]

spec2.json  {"reels": [{"id", "hook", "music": [fid, start_s], "segments": [[src, start_s, secs, text, cx?], ...], "end": [l1, l2]}]}
            src is a footage.json id ("f05", real) or an AI clip id ("c07"); cx (0..1) picks the horizontal crop centre.
footage.json  id -> {license, artist, label, ...}; files are src_dir/<id>.mp4|.webm|.ogv|.ogg|.mp3 (any container ffmpeg reads),
            or .jpg/.png for photos, which get a slow pan (cx and an optional cy, 0..1, pick the framing).

Shots are cut to 1080x1920 with a shared colour grade and 0.3 s crossfades. Handheld footage is stabilised (vidstab),
photos get a slow sub-pixel push-in, and voiceover shots hold at least MIN_SHOT seconds. The music bed is mixed over each shot's own
sound (crowd, dhak) kept low, and loudness-normalised for Instagram. The end card credits every real source.
Needs ffmpeg and Pillow; fonts/Poppins-*.ttf next to this file or in ./fonts.
"""
import glob, json, os, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

W, H, FPS, XF = 1080, 1920, 30, 0.3
HANDLE = "@pujoparikrama.guide"
FONTS = next((d for d in ("fonts", os.path.join(os.path.dirname(__file__), "fonts")) if os.path.isdir(d)), "fonts")
font = lambda w, s: ImageFont.truetype(os.path.join(FONTS, f"Poppins-{w}.ttf"), s)
# Bengali needs raqm shaping; Galada for display lines, Hind Siliguri for the rest (fonts/ from run3.sh)
bnfont = lambda name, s: ImageFont.truetype(os.path.join(FONTS, name), s, layout_engine=ImageFont.Layout.RAQM)
RED, GOLD, CREAM, MAROON, INK = (179, 18, 46), (232, 176, 75), (255, 244, 224), (122, 16, 32), (58, 34, 22)
GRADE = "eq=contrast=1.06:saturation=1.12:gamma=0.98,unsharp=5:5:0.4"


def run(*a):
    r = subprocess.run(a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if r.returncode:
        raise SystemExit(f"ffmpeg failed: {' '.join(a[:6])}…\n{r.stderr[-1500:]}")
    return r.stdout


def src_file(d, sid):
    f = [p for p in glob.glob(f"{d}/{sid}.*") if not p.endswith(".part")]
    if not f:
        raise SystemExit(f"missing source {sid}")
    return f[0]


def has_audio(path):
    return bool(run("ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", path).strip())


def plain(text):
    """Poppins has no emoji glyphs: keep them for Instagram captions, drop them from text drawn on video."""
    return re.sub(r"[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F\u200D]", "", text or "").strip()


def wrap(d, text, f, width):
    words, lines, cur = plain(text).split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + [cur] if cur else lines


def caption_png_bn(path, bn, en, hook=False):
    """Bengali-first overlay: পুজো পরিক্রমা mark, a big Bengali line, the English line smaller under it."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("L", (1, 900))
    for y in range(900):
        grad.putpixel((0, y), int(175 * (1 - y / 900) ** 1.3))
    im.paste((25, 5, 8, 255), (0, 0, W, 900), grad.resize((W, 900)))
    d = ImageDraw.Draw(im)
    d.text((70, 104), "পুজো পরিক্রমা", font=bnfont("Galada-Regular.ttf", 46), fill=CREAM + (240,))
    d.text((W - 70 - d.textlength(HANDLE, font=font("SemiBold", 26)), 118), HANDLE, font=font("SemiBold", 26), fill=GOLD + (230,))
    y = 220
    if bn:
        f = bnfont("Galada-Regular.ttf", 104) if hook else bnfont("HindSiliguri-Bold.ttf", 76)
        lines = wrap(d, bn, f, W - 140)
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
        yy = y
        for ln in lines:
            sd.text((72, yy + 4), ln, font=f, fill=(0, 0, 0, 210)); yy += int(f.size * 1.25)
        im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(7)))
        for ln in lines:
            d.text((70, y), ln, font=f, fill=(255, 255, 255, 255)); y += int(f.size * 1.25)
        y += 6
    if en:
        fe = font("SemiBold", 40 if hook else 36)
        for ln in wrap(d, en, fe, W - 140):
            d.text((72, y + 2), ln, font=fe, fill=(0, 0, 0, 160)); d.text((70, y), ln, font=fe, fill=GOLD + (255,)); y += int(fe.size * 1.3)
    if hook:
        d.rectangle((70, y + 16, 230, y + 26), fill=RED + (255,))
    im.save(path)


def end_png_bn(path, bn, en, credits):
    """Laal-paar end card: cream paper, red sari border with a gold line, Bengali first."""
    im = Image.new("RGB", (W, H), CREAM); d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=tuple(int(a + (b - a) * t) for a, b in zip((255, 246, 228), (240, 220, 186))))
    d.rectangle((0, 0, W - 1, H - 1), outline=RED, width=30)
    d.rectangle((36, 36, W - 37, H - 37), outline=GOLD, width=4)
    import math
    cx, cy, r = W // 2, 470, 120
    for k in range(12):
        a = 2 * math.pi * k / 12; px, py = cx + r * math.cos(a), cy + r * math.sin(a)
        d.ellipse((px - 34, py - 34, px + 34, py + 34), outline=RED, width=4)
    d.ellipse((cx - 66, cy - 66, cx + 66, cy + 66), outline=RED, width=4); d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=RED)
    d.text((W / 2 - d.textlength("পুজো পরিক্রমা", font=bnfont("Galada-Regular.ttf", 58)) / 2, 150), "পুজো পরিক্রমা",
           font=bnfont("Galada-Regular.ttf", 58), fill=MAROON)
    y = 700
    f = bnfont("Galada-Regular.ttf", 110)
    for ln in wrap(d, bn, f, W - 180):
        d.text((W / 2 - d.textlength(ln, font=f) / 2, y), ln, font=f, fill=MAROON); y += 132
    y += 10
    fe = font("Medium", 42)
    for ln in wrap(d, en, fe, W - 200):
        d.text((W / 2 - d.textlength(ln, font=fe) / 2, y), ln, font=fe, fill=INK); y += 58
    y += 40
    fb = font("ExtraBold", 50)
    tw = d.textlength("Link in bio", font=fb)
    d.rounded_rectangle((W / 2 - tw / 2 - 60, y, W / 2 + tw / 2 + 60, y + 112), radius=56, fill=RED)
    d.text((W / 2 - tw / 2, y + 22), "Link in bio", font=fb, fill=CREAM)
    fh = font("SemiBold", 40)
    d.text((W / 2 - d.textlength(HANDLE, font=fh) / 2, y + 150), HANDLE, font=fh, fill=MAROON)
    y = 1560
    fc = font("Medium", 23)
    for ln in wrap(d, credits, fc, W - 200)[:8]:
        d.text((100, y), ln, font=fc, fill=INK); y += 32
    im.save(path)


def outlined(d, xy, text, f, fill=(255, 255, 255, 255), stroke=6):
    d.text(xy, text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 235))


def subtitle_png(path, bn, en, hook=None, end=None):
    """Voiceover look: what is being said as a subtitle in the lower third (Bengali, English under it), a big hook on
    the first shot, a small পুজো পরিক্রমা mark. No bars or boxes: outlined type straight on the footage."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(sh)
    d = ImageDraw.Draw(im)
    mark = bnfont("Galada-Regular.ttf", 44)
    outlined(d, (64, 110), "পুজো পরিক্রমা", mark, stroke=3)
    if end:  # closing question over the last shot, with the call to action
        for y in range(H // 3, H):  # soft shadow so the closing lines read on any footage
            sd.line((0, y, W, y), fill=(0, 0, 0, int(170 * ((y - H / 3) / (H * 2 / 3)) ** 0.8)))
        im = Image.alpha_composite(sh, im); d = ImageDraw.Draw(im)
        f = bnfont("Galada-Regular.ttf", 104)
        lines = wrap(d, end[0], f, W - 150)
        y = 1080 - len(lines) * 62
        for ln in lines:
            outlined(d, ((W - d.textlength(ln, font=f)) / 2, y), ln, f, stroke=5); y += 130
        fe = font("SemiBold", 42)
        for ln in wrap(d, end[1], fe, W - 180):
            outlined(d, ((W - d.textlength(ln, font=fe)) / 2, y + 10), ln, fe, fill=GOLD + (255,), stroke=4); y += 58
        fb = font("ExtraBold", 46); tw = d.textlength("Plan free · link in bio", font=fb)
        d.rounded_rectangle(((W - tw) / 2 - 50, y + 60, (W + tw) / 2 + 50, y + 162), radius=51, fill=(255, 255, 255, 245))
        d.text(((W - tw) / 2, y + 82), "Plan free · link in bio", font=fb, fill=(26, 13, 10))
        fh = font("SemiBold", 36)
        outlined(d, ((W - d.textlength(HANDLE, font=fh)) / 2, y + 200), HANDLE, fh, stroke=3)
        im.save(path); return
    if hook:
        f = bnfont("Galada-Regular.ttf", 118)
        y = 300
        for ln in wrap(d, hook[0], f, W - 140):
            outlined(d, ((W - d.textlength(ln, font=f)) / 2, y), ln, f, stroke=7); y += 148
        fe = font("ExtraBold", 50)
        for ln in wrap(d, hook[1], fe, W - 160):
            outlined(d, ((W - d.textlength(ln, font=fe)) / 2, y + 8), ln, fe, fill=GOLD + (255,), stroke=5); y += 64
    if hook:  # the hook already says it; a subtitle repeating it would crowd the first frame
        bn = en = None
    y = 1360
    if bn:
        f = bnfont("HindSiliguri-Bold.ttf", 66)
        for ln in wrap(d, bn, f, W - 160)[:3]:
            outlined(d, ((W - d.textlength(ln, font=f)) / 2, y), ln, f, stroke=6); y += 86
    if en:
        fe = font("SemiBold", 36)
        for ln in wrap(d, en, fe, W - 180)[:2]:
            outlined(d, ((W - d.textlength(ln, font=fe)) / 2, y + 6), ln, fe, fill=(255, 226, 150, 255), stroke=4); y += 48
    im.save(path)


def caption_png(path, text, hook=False):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("L", (1, 760))
    for y in range(760):
        grad.putpixel((0, y), int(150 * (1 - y / 760) ** 1.4))
    im.paste((0, 0, 0, 255), (0, 0, W, 760), grad.resize((W, 760)))
    d = ImageDraw.Draw(im)
    d.text((70, 120), "Pujo Parikrama 2026  ·  " + HANDLE, font=font("SemiBold", 30), fill=(253, 230, 138, 235))
    if text:
        f = font("ExtraBold", 84 if hook else 68)
        lines, y = wrap(d, text, f, W - 140), 230
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
        for ln in lines:
            sd.text((72, y + 4), ln, font=f, fill=(0, 0, 0, 200)); y += int(f.size * 1.18)
        im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)))
        y = 230
        for ln in lines:
            d.text((70, y), ln, font=f, fill=(255, 255, 255, 255)); y += int(f.size * 1.18)
        if hook:
            d.rectangle((70, y + 18, 230, y + 30), fill=(253, 230, 138, 255))
    im.save(path)


def end_png(path, l1, l2, credits):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H
        d.line((0, y, W, y), fill=tuple(int(a + (b - a) * t) for a, b in zip((159, 18, 57), (124, 45, 18))))
    for r, c in ((460, (201, 92, 80)), (340, (190, 70, 70)), (220, (180, 55, 62))):
        d.ellipse((W - 120 - r, 140 - r, W - 120 + r, 140 + r), outline=c, width=5)
    d.text((90, 600), "Pujo Parikrama 2026", font=font("Bold", 52), fill=(253, 230, 138))
    y = 700
    for ln in wrap(d, l1, font("ExtraBold", 92), W - 180):
        d.text((90, y), ln, font=font("ExtraBold", 92), fill="white"); y += 110
    y += 20
    for ln in wrap(d, l2, font("Medium", 46), W - 180):
        d.text((90, y), ln, font=font("Medium", 46), fill="white"); y += 62
    y += 50
    d.rounded_rectangle((90, y, 600, y + 120), radius=60, fill=(253, 230, 138))
    d.text((150, y + 26), "Link in bio", font=font("ExtraBold", 54), fill=(127, 29, 29))
    d.text((90, y + 170), HANDLE, font=font("SemiBold", 44), fill="white")
    y = 1560
    for ln in wrap(d, credits, font("Medium", 24), W - 180)[:8]:
        d.text((90, y), ln, font=font("Medium", 24), fill=(255, 225, 225)); y += 34
    im.save(path)


PAN = 1.12  # photos are cut 12% larger than the frame and drift across it


def still(path, out, cx, cy):
    """Photo → PAN×frame-sized image cropped around (cx, cy), ready for a slow pan."""
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    bw, bh = round(W * PAN) // 2 * 2, round(H * PAN) // 2 * 2
    k = max(bw / im.width, bh / im.height)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    x = min(max(0, round(im.width * cx - bw / 2)), im.width - bw)
    y = min(max(0, round(im.height * cy - bh / 2)), im.height - bh)
    im.crop((x, y, x + bw, y + bh)).save(out, quality=95)
    return bw - W, bh - H


def ease(u):
    return u * u * (3 - 2 * u)  # smoothstep: the move starts and ends at rest


def still_motion(jpg, out, secs, i):
    """A slow, sub-pixel push-in on a photo, drawn frame by frame (ffmpeg's crop/zoompan move in whole pixels, which
    reads as a judder at this speed). Alternate shots drift left or right a little as they push in."""
    im = Image.open(jpg).convert("RGB")
    n = max(1, round(secs * FPS))
    s0, s1 = min(im.width / W, im.height / H, 1.10), 1.0  # window scale, source px per frame px
    d = 1 if i % 2 else -1
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "12",
                          "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for k in range(n):
        u = ease(k / max(1, n - 1))
        sc = s0 + (s1 - s0) * u
        cx = im.width / 2 + d * 0.25 * (im.width - W * sc) * (u - 0.5)
        cy = im.height / 2 - 0.15 * (im.height - H * sc) * (u - 0.5)
        x0, y0 = cx - W * sc / 2, cy - H * sc / 2
        fr = im.transform((W, H), Image.AFFINE, (sc, 0, x0, 0, sc, y0), resample=Image.BICUBIC)
        p.stdin.write(fr.tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"ffmpeg failed writing {out}")
    return out


def has_filter(name, _cache={}):
    if name not in _cache:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        _cache[name] = f" {name} " in r.stdout
    return _cache[name]


def steady(path, start, secs, out, trf):
    """Handheld phone footage → the same shot on a calm, gliding camera: vidstab finds the shake in a first pass, the
    second pass removes it (2 s of smoothing each way, so a short shot is close to a tripod shot) and zooms in just
    enough to hide the moving edges."""
    cut = ["-ss", str(start), "-t", f"{secs + 0.2:.2f}", "-i", path]
    if has_filter("vidstabdetect"):
        run("ffmpeg", "-y", "-v", "error", *cut, "-vf", f"vidstabdetect=shakiness=10:accuracy=15:stepsize=4:result={trf}", "-f", "null", "-")
        vf = f"vidstabtransform=input={trf}:smoothing=60:optzoom=1:interpol=bicubic,unsharp=5:5:0.5"
    else:
        vf = "deshake=rx=48:ry=48"
    aud = ["-c:a", "aac", "-b:a", "192k"] if has_audio(path) else ["-an"]
    run("ffmpeg", "-y", "-v", "error", *cut, "-vf", vf, *aud, "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-pix_fmt", "yuv420p", out)
    return out


def segment(src_dir, footage, i, seg, reel, tmp):
    sid, start, secs, text, *rest = seg
    cx = rest[0] if rest else 0.5
    cy = rest[1] if len(rest) > 1 else 0.45
    path = src_file(src_dir, sid)
    png, out = f"{tmp}/{reel['id']}_{i}.png", f"{tmp}/{reel['id']}_{i}.mp4"
    hook = i == 0 and bool(reel.get("hook"))
    bn = reel.get("bn")
    if reel.get("vo_files") is not None:  # voiceover reel: subtitles of what is said
        vo = reel["vo"]
        if seg is reel.get("_end_seg"):
            subtitle_png(png, None, None, end=(bn["end"] if bn else reel["end"][0], reel["end"][0] if bn else reel["end"][1]))
        else:
            subtitle_png(png, vo["lines"][i], vo.get("en", [""] * len(vo["lines"]))[i] or text,
                         hook=(bn["hook"], reel["hook"]) if hook and bn else None)
    elif bn:  # Bengali-first look (spec3 reels with a "bn" block)
        caption_png_bn(png, bn["hook"] if hook else bn["segs"][i], reel["hook"] if hook else text, hook=hook)
    else:
        caption_png(png, reel["hook"] if hook else text, hook=hook)
    if path.lower().endswith((".jpg", ".jpeg", ".png")):
        jpg = f"{tmp}/{reel['id']}_{i}_still.jpg"
        still(path, jpg, cx, cy)
        path = still_motion(jpg, f"{tmp}/{reel['id']}_{i}_move.mp4", secs, i)
        crop = "null"
        args = ["ffmpeg", "-y", "-t", str(secs), "-i", path, "-i", png]
    else:
        if (footage.get(sid) or {}).get("source") != "AI":  # real handheld footage gets steadied; AI clips are smooth
            path = steady(path, start, secs, f"{tmp}/{reel['id']}_{i}_steady.mp4", f"{tmp}/{reel['id']}_{i}.trf")
            start = 0
        crop = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={W}:{H}:'max(0,min(iw-{W},iw*{cx}-{W}/2))':'(ih-{H})/2',tpad=stop_mode=clone:stop_duration=4")
        args = ["ffmpeg", "-y", "-ss", str(start), "-t", str(secs), "-i", path, "-i", png]
    v = f"[0:v]{crop},fps={FPS},setsar=1,{GRADE}[v];[v][1:v]overlay=0:0,format=yuv420p[vo]"
    if has_audio(path):
        a = "[0:a]aresample=48000,aformat=channel_layouts=stereo,apad[ao]"
    else:
        args += ["-f", "lavfi", "-t", str(secs), "-i", "anullsrc=r=48000:cl=stereo"]
        a = "[2:a]anull[ao]"
    run(*args, "-filter_complex", f"{v};{a}", "-map", "[vo]", "-map", "[ao]", "-t", str(secs),
        "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-c:a", "aac", "-b:a", "192k", out)
    return out, secs


def credits_for(reel, footage):
    seen, parts, ai = [], [], False
    for seg in reel["segments"]:
        sid = seg[0]
        if sid.startswith("c") and sid not in footage or footage.get(sid, {}).get("source") == "AI":
            ai = True
        elif sid not in seen:
            seen.append(sid)
    by_artist = {}
    for sid in seen:
        f = footage[sid]
        src = f.get("source", "Wikimedia Commons")
        lic = f["license"] if src == "Wikimedia Commons" else src  # Pexels / Pixabay licences need no attribution; we credit anyway
        by_artist.setdefault((f["artist"] or "Unknown", lic), []).append(sid)
    for (artist, lic), _ in by_artist.items():
        parts.append(f"{artist} ({lic})")
    m = reel.get("music") if not reel.get("vo") else None
    if m:
        f = footage[m[0]]
        parts.append(f"Music: {f['label'].replace(' (audio)', '')}" + (f", {f['artist']}" if f["artist"] else "") + f" ({f['license']})")
    srcs = sorted({footage[s].get("source", "Wikimedia Commons") for s in seen}) or ["Wikimedia Commons"]
    txt = f"Footage: {', '.join(srcs)} — " + "; ".join(parts) if parts else "Footage: Wikimedia Commons"
    if ai:
        txt += ". Some scenes are AI-generated recreations."
    return txt


def duration(path):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path).strip())


VO_LEAD, VO_TAIL, END_S = 0.35, 0.9, 3.6
MIN_SHOT, HOOK_SHOT = 5.0, 5.5  # every shot holds long enough to be taken in; the first one a little longer


def fit_start(footage, sid, start, secs):
    """Moves a cut earlier when a longer voiceover line would run it past the end of its clip."""
    dur = (footage.get(sid) or {}).get("dur") or 0
    return round(max(0.0, min(start, dur - secs - 0.1)), 2) if dur else start


def build_vo(reel, footage, src_dir, out_dir, tmp):
    """Voiceover reel: one spoken Bengali line per shot (reel["vo_files"], aligned with the segments), hard cuts timed
    to the lines, the shots' own sound low underneath, no music. The last shot runs on under the closing question."""
    segs, offs, t = [], [], 0.0
    for i, seg in enumerate(reel["segments"]):
        f = reel["vo_files"][i] if i < len(reel["vo_files"]) else None
        d = duration(f) if f else 0
        secs = round(max(seg[2], HOOK_SHOT if i == 0 else MIN_SHOT, VO_LEAD + d + VO_TAIL), 2)
        segs.append([seg[0], fit_start(footage, seg[0], seg[1], secs), secs, *seg[3:]])
        offs.append((f, t + VO_LEAD) if f else None)
        t += secs
    if reel.get("end"):
        last = segs[-1]
        ec = reel.get("end_clip") or [last[0], last[1] + last[2]]  # by default the last shot simply runs on
        endseg = [ec[0], fit_start(footage, ec[0], ec[1], END_S), END_S, "", *(ec[2:] or last[4:])]
        segs.append(endseg)
        reel["_end_seg"] = endseg
    r2 = dict(reel, segments=segs)
    parts = [segment(src_dir, footage, i, sg, r2, tmp) for i, sg in enumerate(segs)]
    total = sum(d for _, d in parts)
    ins = []
    for p_, _ in parts:
        ins += ["-i", p_]
    n = len(parts)
    fc = ["".join(f"[{k}:v][{k}:a]" for k in range(n)) + f"concat=n={n}:v=1:a=1[v][nat0]",
          "[nat0]volume=0.22[nat]"]
    vo = [x for x in offs if x]
    for j, (f, at) in enumerate(vo):
        ins += ["-i", f]
        ms = int(at * 1000)
        fc.append(f"[{n + j}:a]aresample=48000,aformat=channel_layouts=stereo,volume=1.0,adelay={ms}|{ms}[vo{j}]")
    mix = "".join(f"[vo{j}]" for j in range(len(vo)))
    fc.append(f"[nat]{mix}amix=inputs={len(vo) + 1}:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    run("ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[aout]", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-maxrate", "14M", "-bufsize", "28M", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart", f"{out_dir}/{reel['id']}.mp4")
    write_caption(reel, footage, out_dir)
    return total


def write_caption(reel, footage, out_dir):
    c = reel.get("caption")
    if c:  # Instagram caption: Bengali, English, hashtags, then the attribution the CC licences require
        credit = "🎥 Credits — " + credits_for(reel, footage).replace("Footage: ", "", 1)
        if reel.get("vo"):
            credit = credit + ". Voiceover: " + reel["vo"].get("credit", "AI voice (ElevenLabs)")
        sa = " This reel: CC BY-SA 4.0." if any("SA" in footage[x[0]]["license"] for x in reel["segments"] if x[0] in footage) else ""
        handles = sorted({footage[x[0]]["artist"] for x in reel["segments"]
                          if footage.get(x[0], {}).get("license") == "used with permission"})
        if handles:  # creators who shared their clips: thank them by handle, first thing after the hook
            c = dict(c, bn=c["bn"] + "\n\n🎥 " + " ".join(handles) + "-কে অনেক ধন্যবাদ!")
        with open(f"{out_dir}/{reel['id']}.caption.txt", "w", encoding="utf-8") as f:
            f.write(f"{c['bn']}\n\n{c['en']}\n\n{c['tags']}\n\n{credit}.{sa}\n".replace("..", "."))  # Bengali first


def build(reel, footage, src_dir, out_dir, tmp):
    if reel.get("vo_files") is not None:
        return build_vo(reel, footage, src_dir, out_dir, tmp)
    parts = [segment(src_dir, footage, i, s, reel, tmp) for i, s in enumerate(reel["segments"])]
    if reel.get("end"):  # video stories have no end card
        endp, endv = f"{tmp}/{reel['id']}_end.png", f"{tmp}/{reel['id']}_end.mp4"
        if reel.get("bn"):
            end_png_bn(endp, reel["bn"]["end"], reel["end"][1], credits_for(reel, footage))
        else:
            end_png(endp, *reel["end"], credits_for(reel, footage))
        run("ffmpeg", "-y", "-loop", "1", "-t", "3.2", "-i", endp, "-f", "lavfi", "-t", "3.2", "-i", "anullsrc=r=48000:cl=stereo",
            "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-shortest", endv)
        parts.append((endv, 3.2))
    # crossfade chain
    ins, fc, off = [], [], 0.0
    for p, _ in parts:
        ins += ["-i", p]
    lv, la = "[0:v]", "[0:a]"
    for k in range(1, len(parts)):
        off += parts[k - 1][1] - XF
        fc.append(f"{lv}[{k}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[v{k}]")
        fc.append(f"{la}[{k}:a]acrossfade=d={XF}[a{k}]")
        lv, la = f"[v{k}]", f"[a{k}]"
    total = sum(d for _, d in parts) - XF * (len(parts) - 1)
    mix = f"{la}volume=0.35[nat]"
    m = reel.get("music")
    if m:
        ins += ["-ss", str(m[1]), "-t", f"{total:.2f}", "-i", src_file(src_dir, m[0])]
        mi = len(parts)
        mix += (f";[{mi}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.6,"
                f"afade=t=out:st={total - 2:.2f}:d=2,volume=1.0[mus];[mus][nat]amix=inputs=2:duration=first:normalize=0[mx]")
        last = "[mx]"
    else:
        last = "[nat]"
    mix += f";{last}loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
    run("ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc + [mix]), "-map", lv if fc else "0:v", "-map", "[aout]", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", f"{out_dir}/{reel['id']}.mp4")
    write_caption(reel, footage, out_dir)
    return total


if __name__ == "__main__":
    spec, fjson, src_dir, out_dir = sys.argv[1:5]
    only = set(sys.argv[5].split(",")) if len(sys.argv) > 5 else None
    footage = json.load(open(fjson))
    tmp = os.path.join(out_dir, "_tmp"); os.makedirs(tmp, exist_ok=True)
    for r in json.load(open(spec))["reels"]:
        if only and r["id"] not in only:
            continue
        print("built", r["id"], round(build(r, footage, src_dir, out_dir, tmp), 1), flush=True)
