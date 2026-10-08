"""Reel version of a card carousel: the same slides, one after another, over the dhak.

    {"id": "r2", "type": "reel", "at": "21:00", "render": "cards_reel", "from": "p3", "hook": "…", "caption": {…}}
"from" names a card carousel (or photo post) earlier in the same day; its rendered slides are reused, so the reel and
the carousel carry the same words. Posting both is the owner's test (8 Oct): which format does this account's audience
take to? Each 1440x1800 slide sits on a 1080x1920 frame over a blurred, darkened copy of itself, holds long enough to
read (more for word-heavy slides) and crossfades into the next. Needs Pillow and ffmpeg.
"""
import subprocess
from pathlib import Path

W, H, FPS = 1080, 1920, 30
FADE = 0.35
AUDIO = Path(__file__).resolve().parents[1] / "app" / "audio" / "dhak.mp3"


def hold(n, k):
    """Seconds on slide k of n: the cover is a glance, the middle is reading, the ask lingers."""
    return 2.4 if k == 0 else 3.0 if k == n - 1 else 3.4


def frame(slide):
    from PIL import Image, ImageFilter
    im = Image.open(slide).convert("RGB")
    bg = im.resize((W, round(W * im.height / im.width))).resize((W, H)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.55)
    fg = im.resize((W, round(W * im.height / im.width)), Image.LANCZOS)
    bg.paste(fg, (0, (H - fg.height) // 2))
    return bg


def render(slides, out, tmp):
    """slides: paths in order → out mp4; returns seconds."""
    tmp = Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    n = len(slides)
    durs = [hold(n, k) + (FADE if 0 < k < n - 1 else FADE / 2) for k in range(n)]
    args = ["ffmpeg", "-y", "-v", "error"]
    for k, s in enumerate(slides):
        png = tmp / f"cr-{k:02d}.png"
        frame(s).save(png)
        args += ["-loop", "1", "-t", f"{durs[k]:.2f}", "-framerate", str(FPS), "-i", str(png)]
    total = sum(durs) - FADE * (n - 1)
    args += ["-ss", "2", "-i", str(AUDIO)]
    chain, last, offset = [], "[0:v]", 0.0
    for k in range(1, n):
        offset += durs[k - 1] - FADE
        lab = f"[v{k}]"
        chain.append(f"{last}[{k}:v]xfade=transition=fade:duration={FADE}:offset={offset:.2f}{lab}")
        last = lab
    chain.append(f"{last}format=yuv420p[vo]")
    chain.append(f"[{n}:a]afade=t=in:d=0.3,afade=t=out:st={total - 1.2:.2f}:d=1.2,volume=0.9[ao]")
    args += ["-filter_complex", ";".join(chain), "-map", "[vo]", "-map", "[ao]", "-t", f"{total:.2f}", "-r", str(FPS),
             "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-movflags", "+faststart",
             "-c:a", "aac", "-b:a", "160k", str(out)]
    if subprocess.run(args).returncode:
        raise SystemExit(f"ffmpeg failed for {out}")
    return round(total, 2)
