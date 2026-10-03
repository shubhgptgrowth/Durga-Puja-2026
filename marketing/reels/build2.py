"""Build Instagram Reels from real CC-licensed footage (Wikimedia Commons) plus a few AI shots, with music and credits.

    python3 build2.py spec2.json footage.json src_dir out_dir [reel_id,...]

spec2.json  {"reels": [{"id", "hook", "music": [fid, start_s], "segments": [[src, start_s, secs, text, cx?], ...], "end": [l1, l2]}]}
            src is a footage.json id ("f05", real) or an AI clip id ("c07"); cx (0..1) picks the horizontal crop centre.
footage.json  id -> {license, artist, label, ...}; files are src_dir/<id>.mp4|.webm|.ogv|.ogg|.mp3 (any container ffmpeg reads).

Shots are cut to 1080x1920 with a shared colour grade and 0.3 s crossfades. The music bed is mixed over each shot's own
sound (crowd, dhak) kept low, and loudness-normalised for Instagram. The end card credits every real source.
Needs ffmpeg and Pillow; fonts/Poppins-*.ttf next to this file or in ./fonts.
"""
import glob, json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, XF = 1080, 1920, 30, 0.3
HANDLE = "@pujoparikrama.guide"
FONTS = next(d for d in ("fonts", os.path.join(os.path.dirname(__file__), "fonts")) if os.path.isdir(d))
font = lambda w, s: ImageFont.truetype(os.path.join(FONTS, f"Poppins-{w}.ttf"), s)
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


def wrap(d, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur); cur = w
    return lines + [cur] if cur else lines


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


def segment(src_dir, footage, i, seg, reel, tmp):
    sid, start, secs, text, *rest = seg
    cx = rest[0] if rest else 0.5
    path = src_file(src_dir, sid)
    png, out = f"{tmp}/{reel['id']}_{i}.png", f"{tmp}/{reel['id']}_{i}.mp4"
    hook = i == 0 and bool(reel.get("hook"))
    caption_png(png, reel["hook"] if hook else text, hook=hook)
    crop = (f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={W}:{H}:'max(0,min(iw-{W},iw*{cx}-{W}/2))':'(ih-{H})/2'")
    v = f"[0:v]{crop},fps={FPS},setsar=1,{GRADE}[v];[v][1:v]overlay=0:0,format=yuv420p[vo]"
    args = ["ffmpeg", "-y", "-ss", str(start), "-t", str(secs), "-i", path, "-i", png]
    if has_audio(path):
        a = "[0:a]aresample=48000,aformat=channel_layouts=stereo,apad[ao]"
    else:
        args += ["-f", "lavfi", "-t", str(secs), "-i", "anullsrc=r=48000:cl=stereo"]
        a = "[2:a]anull[ao]"
    run(*args, "-filter_complex", f"{v};{a}", "-map", "[vo]", "-map", "[ao]", "-t", str(secs),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", out)
    return out, secs


def credits_for(reel, footage):
    seen, parts, ai = [], [], False
    for seg in reel["segments"]:
        sid = seg[0]
        if sid.startswith("c"):
            ai = True
        elif sid not in seen:
            seen.append(sid)
    by_artist = {}
    for sid in seen:
        f = footage[sid]
        by_artist.setdefault((f["artist"] or "Unknown", f["license"]), []).append(sid)
    for (artist, lic), _ in by_artist.items():
        parts.append(f"{artist} ({lic})")
    m = reel.get("music")
    if m:
        f = footage[m[0]]
        parts.append(f"Music: {f['label'].replace(' (audio)', '')}" + (f", {f['artist']}" if f["artist"] else "") + f" ({f['license']})")
    txt = "Footage: Wikimedia Commons — " + "; ".join(parts)
    if ai:
        txt += ". Some shots AI-generated."
    return txt


def build(reel, footage, src_dir, out_dir, tmp):
    parts = [segment(src_dir, footage, i, s, reel, tmp) for i, s in enumerate(reel["segments"])]
    endp, endv = f"{tmp}/{reel['id']}_end.png", f"{tmp}/{reel['id']}_end.mp4"
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
    run("ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc) + ";" + mix, "-map", lv, "-map", "[aout]", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart", f"{out_dir}/{reel['id']}.mp4")
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
