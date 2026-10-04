"""Stitch AI-generated 9:16 clips into captioned Instagram Reels (no audio: add trending audio in Instagram).

    python3 build.py spec.json clips_dir out_dir

spec.json: {"reels": [{"id", "hook", "segments": [[clip, seconds, text, start?], ...], "end": [line1, line2]}]}
Clips are <clip>.mp4 in clips_dir. Text is drawn with Pillow (English only; captions carry the Bengali).
Needs ffmpeg and Pillow, and fonts/Poppins-*.ttf next to this file or in ./fonts.
"""
import json, os, subprocess, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
HANDLE = "@pujoparikrama.guide"
FONTS = next(d for d in ("fonts", os.path.join(os.path.dirname(__file__), "fonts")) if os.path.isdir(d))
font = lambda w, s: ImageFont.truetype(os.path.join(FONTS, f"Poppins-{w}.ttf"), s)


def wrap(d, text, f, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width: cur = t
        else: lines.append(cur); cur = w
    return lines + [cur] if cur else lines


def caption_png(path, text, hook=False):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("L", (1, 760))
    for y in range(760): grad.putpixel((0, y), int(150 * (1 - y / 760) ** 1.4))
    im.paste((0, 0, 0, 255), (0, 0, W, 760), grad.resize((W, 760)))
    d = ImageDraw.Draw(im)
    d.text((70, 120), "Pujo Parikrama 2026  ·  " + HANDLE, font=font("SemiBold", 30), fill=(253, 230, 138, 235))
    if text:
        f = font("ExtraBold", 84 if hook else 68)
        lines = wrap(d, text, f, W - 140)
        y = 230
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sd = ImageDraw.Draw(shadow)
        for ln in lines:
            sd.text((72, y + 4), ln, font=f, fill=(0, 0, 0, 200)); y += int(f.size * 1.18)
        im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6)))
        y = 230
        for ln in lines:
            d.text((70, y), ln, font=f, fill=(255, 255, 255, 255)); y += int(f.size * 1.18)
        if hook: d.rectangle((70, y + 18, 230, y + 30), fill=(253, 230, 138, 255))
    im.save(path)


def end_png(path, l1, l2):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / H; c = [int(a + (b - a) * t) for a, b in zip((159, 18, 57), (124, 45, 18))]
        d.line((0, y, W, y), fill=tuple(c))
    for r, c in ((460, (201, 92, 80)), (340, (190, 70, 70)), (220, (180, 55, 62))):
        d.ellipse((W - 120 - r, 140 - r, W - 120 + r, 140 + r), outline=c, width=5)
    d.text((90, 640), "Pujo Parikrama 2026", font=font("Bold", 52), fill=(253, 230, 138))
    y = 740
    for ln in wrap(d, l1, font("ExtraBold", 92), W - 180):
        d.text((90, y), ln, font=font("ExtraBold", 92), fill="white"); y += 110
    y += 20
    for ln in wrap(d, l2, font("Medium", 46), W - 180):
        d.text((90, y), ln, font=font("Medium", 46), fill=(255, 255, 255)); y += 62
    y += 50
    d.rounded_rectangle((90, y, 600, y + 120), radius=60, fill=(253, 230, 138))
    d.text((150, y + 26), "Link in bio", font=font("ExtraBold", 54), fill=(127, 29, 29))
    d.text((90, y + 180), HANDLE, font=font("SemiBold", 44), fill=(255, 255, 255))
    im.save(path)


def run(*a): subprocess.run(a, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def build(reel, clips, out, tmp):
    parts = []
    for i, (clip, secs, text, *start) in enumerate(reel["segments"]):
        png, seg = f"{tmp}/{reel['id']}_{i}.png", f"{tmp}/{reel['id']}_{i}.mp4"
        caption_png(png, reel["hook"] if i == 0 and reel.get("hook") else text, hook=i == 0 and bool(reel.get("hook")))
        run("ffmpeg", "-y", "-ss", str(start[0] if start else 0.2), "-t", str(secs), "-i", f"{clips}/{clip}.mp4", "-i", png, "-filter_complex",
            f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1[v];[v][1:v]overlay=0:0,format=yuv420p",
            "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", seg)
        parts.append(seg)
    endp, endv = f"{tmp}/{reel['id']}_end.png", f"{tmp}/{reel['id']}_end.mp4"
    end_png(endp, *reel["end"])
    run("ffmpeg", "-y", "-loop", "1", "-t", "2.6", "-i", endp, "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", endv)
    parts.append(endv)
    lst = f"{tmp}/{reel['id']}.txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(p)}'\n" for p in parts))
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", f"{out}/{reel['id']}.mp4")


if __name__ == "__main__":
    spec, clips, out = sys.argv[1:4]
    tmp = os.path.join(out, "_tmp"); os.makedirs(tmp, exist_ok=True)
    only = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
    for r in json.load(open(spec))["reels"]:
        if only and r["id"] not in only: continue
        build(r, clips, out, tmp); print("built", r["id"], flush=True)
