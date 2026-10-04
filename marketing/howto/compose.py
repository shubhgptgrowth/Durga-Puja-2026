"""Builds the 'how to use the app' video (1080×1920, about 40 s) from the screen recording made by record.cjs.

    python3 compose.py <rec dir> <fonts dir> <assets dir> <out.mp4> [voiceover dir]

With a voiceover dir (vo_00.mp3 for the intro, vo_01…vo_06 for the app scenes, vo_07 for the end card), each line
starts just after its scene appears, a scene is held on its last frame if the line runs longer, and the music
ducks under the voice.

The video opens on a real Durga photo with a Bengali hook. Each app scene then sits in a phone frame on maroon, with a
numbered Bengali caption and English under it. It ends on a laal-paar card with the link and the Instagram handle.
The web address stays on screen throughout, so a forwarded copy still says where to go.
Assets: durga.jpg (intro photo), dhak.mp3 and shankh.mp3 (from app/audio). Credits are in SCENES/CREDITS below.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
RED, GOLD, CREAM, MAROON, INK = (178, 24, 38), (232, 178, 58), (251, 243, 228), (74, 10, 20), (43, 20, 16)
SITE = "pujoparikramaguide.in"
IG = "@pujoparikrama.guide"

# Phone frame: the 780×1688 recording scaled into this box.
PH_H = 1440
PH_W = round(PH_H * 780 / 1688 / 2) * 2
PH_X, PH_Y = (W - PH_W) // 2, 372
RADIUS = 44

# scene id → (Bengali caption, English caption, step number shown in the badge or "")
SCENES = [
    ("home", "১০৭টা প্যান্ডেল, এক জায়গায়", "Kolkata's pujo, in one free guide", ""),
    ("plan", "এলাকা বাছুন, রুট তৈরি", "Pick your areas and get a walking route", "১"),
    ("explore", "কখন ভিড় কম, দেখে নিন", "Least-crowded time for every pandal, and food nearby", "২"),
    ("pandal", "রাস্তা দেখুন, পৌঁছে চেক-ইন", "Metro, bus and auto routes; check in when you arrive", "৩"),
    ("me", "কত হাঁটলেন, কটা ঠাকুর দেখলেন", "Your steps, pandals and badges", "৪"),
    ("bangla", "বাংলাতেও আছে", "In বাংলা, English and हिंदी", ""),
]
CREDITS = ("Photo: Jonoikobangali, CC BY-SA 3.0 · Dhak: Sumita Roy Dutta, CC BY-SA 4.0 · "
           "Shankh: Jyoti Chiring, CC BY 4.0 (Wikimedia Commons)")
INTRO_S, END_S, XF = 3.6, 4.6, 0.3
SPEED = 1.15  # screen scenes play slightly faster than real time
VO_LEAD, VO_TAIL = 0.45, 0.55  # voiceover starts this long into its scene, and the scene runs this long after it

FONTS = None


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size, layout_engine=ImageFont.Layout.RAQM)


def wrap(d, text, f, maxw):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    return lines + [cur] if cur else lines


def centred(d, y, text, f, fill, maxw=W - 120, gap=1.18, **kw):
    for line in wrap(d, text, f, maxw):
        d.text((W / 2, y), line, font=f, fill=fill, anchor="ma", **kw)
        y += f.size * gap
    return y


def border(d, inset=26, w=14):
    """Laal-paar: a red sari border with a thin gold line inside."""
    d.rectangle([inset, inset, W - inset, H - inset], outline=RED, width=w)
    d.rectangle([inset + w + 8, inset + w + 8, W - inset - w - 8, H - inset - w - 8], outline=GOLD, width=3)


def footer(d, y=H - 66, fill=CREAM):
    d.text((W / 2, y), f"{SITE}  ·  {IG}", font=font("Poppins-SemiBold.ttf", 30), fill=fill, anchor="mm")


def scene_bg(bn, en, step, path):
    im = Image.new("RGB", (W, H), MAROON)
    # soft radial glow behind the phone
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([-200, 300, W + 200, H + 200], fill=110)
    im.paste(Image.new("RGB", (W, H), (128, 20, 34)), (0, 0), glow.filter(ImageFilter.GaussianBlur(160)))
    d = ImageDraw.Draw(im)
    d.text((W / 2, 70), "পুজো পরিক্রমা", font=font("Galada-Regular.ttf", 44), fill=GOLD, anchor="mm")
    fb = font("HindSiliguri-Bold.ttf", 66)
    lines = wrap(d, bn, fb, W - (260 if step else 120))
    y = 128
    if step:
        tw = max(d.textlength(l, font=fb) for l in lines)
        cx = W / 2 - tw / 2 - 62
        d.ellipse([cx - 40, y + 4, cx + 40, y + 84], fill=GOLD)
        d.text((cx, y + 44), step, font=font("HindSiliguri-Bold.ttf", 56), fill=MAROON, anchor="mm")
    for line in lines:
        d.text((W / 2 + (22 if step else 0), y), line, font=fb, fill=CREAM, anchor="ma")
        y += 80
    centred(d, y + 8, en, font("Poppins-SemiBold.ttf", 34), GOLD, maxw=W - 140)
    # phone: shadow, bezel, gold rim (the recording is overlaid inside)
    sh = Image.new("L", (W, H), 0)
    ImageDraw.Draw(sh).rounded_rectangle([PH_X - 6, PH_Y + 14, PH_X + PH_W + 6, PH_Y + PH_H + 26], RADIUS + 14, fill=170)
    im.paste((20, 4, 8), (0, 0), sh.filter(ImageFilter.GaussianBlur(26)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([PH_X - 14, PH_Y - 14, PH_X + PH_W + 14, PH_Y + PH_H + 14], RADIUS + 14, fill=(18, 8, 10), outline=GOLD, width=3)
    footer(d, H - 52)
    im.save(path)


def mask(path):
    m = Image.new("L", (PH_W, PH_H), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, PH_W - 1, PH_H - 1], RADIUS, fill=255)
    m.save(path)


def intro_overlay(path):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    grad = Image.new("L", (1, H))
    for y in range(H):
        a = 0 if y < H * 0.42 else int(235 * min(1, (y - H * 0.42) / (H * 0.4)))
        top = int(150 * max(0, 1 - y / 420))
        grad.putpixel((0, y), max(a, top))
    im.paste(Image.new("RGBA", (W, H), (40, 4, 10, 255)), (0, 0), grad.resize((W, H)))
    d = ImageDraw.Draw(im)
    d.text((W / 2, 120), "পুজো পরিক্রমা", font=font("Galada-Regular.ttf", 72), fill=GOLD, anchor="mm")
    y = centred(d, 1250, "ঠাকুর দেখার প্ল্যান?", font("Galada-Regular.ttf", 128), CREAM)
    y = centred(d, y + 10, "এক অ্যাপে, ৩০ সেকেন্ডে", font("HindSiliguri-Bold.ttf", 70), GOLD)
    centred(d, y + 26, "How to plan your pandal hopping, in 30 seconds", font("Poppins-SemiBold.ttf", 38), CREAM, maxw=W - 180)
    footer(d, H - 70)
    im.save(path)


def end_card(path):
    im = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(im)
    border(d)
    # alpona-style rosette
    cx, cy = W / 2, 420
    for r, col in ((150, RED), (118, CREAM), (96, GOLD), (70, CREAM), (44, RED)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
    for k in range(12):
        import math
        a = k * math.pi / 6
        x, y = cx + 132 * math.cos(a), cy + 132 * math.sin(a)
        d.ellipse([x - 14, y - 14, x + 14, y + 14], fill=CREAM, outline=RED, width=4)
    d.text((W / 2, 690), "পুজো পরিক্রমা", font=font("Galada-Regular.ttf", 120), fill=RED, anchor="mm")
    y = centred(d, 800, "এবার ঠাকুর দেখা হোক প্ল্যান করে", font("HindSiliguri-Bold.ttf", 58), MAROON)
    centred(d, y + 6, "Plan your pujo, free", font("Poppins-SemiBold.ttf", 40), INK)
    # link pill
    f = font("Poppins-Bold.ttf", 60)
    tw = d.textlength(SITE, font=f)
    d.rounded_rectangle([W / 2 - tw / 2 - 46, 1110, W / 2 + tw / 2 + 46, 1230], 60, fill=RED)
    d.text((W / 2, 1170), SITE, font=f, fill=CREAM, anchor="mm")
    d.text((W / 2, 1290), "Opens in your browser · nothing to install", font=font("Poppins-SemiBold.ttf", 34), fill=INK, anchor="mm")
    d.text((W / 2, 1420), "Instagram", font=font("Poppins-SemiBold.ttf", 34), fill=RED, anchor="mm")
    d.text((W / 2, 1478), IG, font=font("Poppins-Bold.ttf", 52), fill=MAROON, anchor="mm")
    centred(d, 1600, "বন্ধুদের, পরিবারের গ্রুপে পাঠিয়ে দিন", font("HindSiliguri-Bold.ttf", 44), RED)
    centred(d, H - 150, CREDITS, font("Poppins-Medium.ttf", 21), (110, 80, 70), maxw=W - 200)
    im.save(path)


def run(*a):
    subprocess.run(a, check=True)


def screen_clip(rec, sid, t1, out):
    """Frames → constant-rate clip, each frame held until the next one arrived."""
    frames = sorted((rec / sid).glob("*.jpg"))
    lst = rec / f"{sid}.txt"
    with open(lst, "w") as fh:
        for i, f in enumerate(frames):
            t = float(f.stem.split("_")[1])
            nxt = float(frames[i + 1].stem.split("_")[1]) if i + 1 < len(frames) else t1
            fh.write(f"file '{f.resolve()}'\nduration {max(nxt - t, 0.001):.3f}\n")
        fh.write(f"file '{frames[-1].resolve()}'\n")
    run("ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
        "-vf", f"setpts=PTS/{SPEED},fps={FPS},scale={PH_W}:{PH_H}:flags=lanczos,format=yuv420p",
        "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", str(out))


def dur(f):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)]))


def main(rec, fonts, assets, out, vo=None):
    global FONTS
    rec, FONTS, assets, out = Path(rec), Path(fonts), Path(assets), Path(out)
    tmp = out.parent / "howto_tmp"
    tmp.mkdir(exist_ok=True)
    marks = {s["seg"]: s for s in json.load(open(rec / "scenes.json"))}
    mask(tmp / "mask.png")
    clips = []
    lines = [Path(vo) / f"vo_{k:02d}.mp3" for k in range(len(SCENES) + 2)] if vo else []
    need = [dur(f) + VO_LEAD + VO_TAIL if f.exists() else 0 for f in lines] or [0] * (len(SCENES) + 2)

    # intro: slow push-in on the photo, overlay fades in
    intro_overlay(tmp / "intro.png")
    intro_s = max(INTRO_S, need[0])
    n = int(intro_s * FPS)
    run("ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(assets / "durga.jpg"), "-loop", "1", "-i", str(tmp / "intro.png"),
        "-filter_complex",
        f"[0]scale={W * 2}:{H * 2}:force_original_aspect_ratio=increase,crop={W * 2}:{H * 2},"
        f"zoompan=z='1.0+0.06*on/{n}':x='iw/2-iw/zoom/2':y='ih/2.6-ih/zoom/2.6':d={n}:s={W}x{H}:fps={FPS}[bg];"
        f"[1]format=rgba,fade=in:st=0.35:d=0.6:alpha=1[ov];[bg][ov]overlay=0:0,format=yuv420p",
        "-t", f"{intro_s:.3f}", "-c:v", "libx264", "-crf", "17", "-preset", "veryfast", str(tmp / "c00.mp4"))
    clips.append(tmp / "c00.mp4")

    for i, (sid, bn, en, step) in enumerate(SCENES, 1):
        scene_bg(bn, en, step, tmp / f"bg_{sid}.png")
        screen_clip(rec, sid, marks[sid]["t1"], tmp / f"s_{sid}.mp4")
        d = dur(tmp / f"s_{sid}.mp4")
        hold = max(0.0, need[i] - d)  # freeze the last frame while the voiceover finishes
        run("ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(tmp / f"bg_{sid}.png"), "-i", str(tmp / f"s_{sid}.mp4"),
            "-loop", "1", "-i", str(tmp / "mask.png"),
            "-filter_complex", f"[1]tpad=stop_mode=clone:stop_duration={hold:.3f}[sv];[2]format=gray[m];[sv][m]alphamerge[s];"
                               f"[0][s]overlay={PH_X}:{PH_Y}:shortest=1,format=yuv420p",
            # -t: the looped stills never end on their own
            "-t", f"{d + hold:.3f}", "-r", str(FPS), "-c:v", "libx264", "-crf", "17", "-preset", "veryfast", str(tmp / f"c{i:02d}.mp4"))
        clips.append(tmp / f"c{i:02d}.mp4")

    end_card(tmp / "end.png")
    run("ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(tmp / "end.png"), "-vf", "format=yuv420p", "-r", str(FPS),
        "-t", f"{max(END_S, need[-1]):.3f}", "-c:v", "libx264", "-crf", "17", "-preset", "veryfast", str(tmp / "c99.mp4"))
    clips.append(tmp / "c99.mp4")

    # crossfade the clips together
    durs = [dur(c) for c in clips]
    args, fc, prev, off = [], [], "[0:v]", 0.0
    for c in clips:
        args += ["-i", str(c)]
    for k in range(1, len(clips)):
        off += durs[k - 1] - XF
        lab = f"[x{k}]"
        fc.append(f"{prev}[{k}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}{lab}")
        prev = lab
    total = sum(durs) - XF * (len(clips) - 1)
    # audio: shankh opens, dhak carries it, everything fades out on the end card
    a = len(clips)
    args += ["-i", str(assets / "shankh.mp3"), "-stream_loop", "-1", "-i", str(assets / "dhak.mp3")]
    fc.append(f"[{a}:a]atrim=0:3.2,afade=t=out:st=2.4:d=0.8,volume=0.9[sk]")
    fc.append(f"[{a + 1}:a]atrim=0:{total:.2f},asetpts=PTS-STARTPTS,afade=t=in:d=1.2,"
              f"afade=t=out:st={total - 1.8:.2f}:d=1.8,volume=0.75,adelay=1800|1800[dk]")
    if not lines:
        fc.append(f"[sk][dk]amix=inputs=2:duration=longest:normalize=0,atrim=0:{total:.2f},alimiter=limit=0.9[a]")
    else:
        # each line starts VO_LEAD into its clip; the music ducks under the voice
        fc.append("[sk][dk]amix=inputs=2:duration=longest:normalize=0[mus]")
        start, labs = 0.0, []
        for k, f in enumerate(lines):
            if f.exists():
                args += ["-i", str(f)]
                ms = int((start + VO_LEAD) * 1000)
                fc.append(f"[{a + 2 + len(labs)}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume=1.6[v{k}]")
                labs.append(f"[v{k}]")
            start += durs[k] - XF
        fc.append(f"{''.join(labs)}amix=inputs={len(labs)}:duration=longest:normalize=0,asplit=2[vo1][vo2]")
        fc.append("[mus]aresample=48000,aformat=channel_layouts=stereo[mus2]")
        fc.append("[mus2][vo1]sidechaincompress=threshold=0.015:ratio=12:attack=15:release=450:makeup=1[duck]")
        fc.append(f"[duck][vo2]amix=inputs=2:duration=first:normalize=0,atrim=0:{total:.2f},alimiter=limit=0.92[a]")
    run("ffmpeg", "-v", "error", "-y", *args, "-filter_complex", ";".join(fc), "-map", prev, "-map", "[a]",
        "-c:v", "libx264", "-crf", "21", "-preset", "slow", "-profile:v", "high", "-pix_fmt", "yuv420p",
        "-maxrate", "3M", "-bufsize", "6M", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out))
    print(f"{out} {total:.1f}s {os.path.getsize(out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main(*sys.argv[1:6])
