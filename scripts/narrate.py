"""Recorded narration for the guides' Listen player, in an open-source neural voice (Kokoro, Apache-2.0). Runs in CI.

  python scripts/narrate.py <blocks.json> <out dir> [--voice af_heart] [--shard 0/4]

blocks.json comes from scripts/narration_blocks.mjs (what the player reads on each page). For each page this writes
<out>/<page>/narration.mp3 and narration.json: {v, h, voice, voice_label, duration, blocks: [[start, end] | null, …]}.
`h` is a hash of the page's text (fnv1a below, the same as guide.js), so a page whose text has changed since it was
recorded is re-recorded, and the player never plays a recording that no longer matches. Bengali and Devanagari lines
(mantras) are not spoken (null); the player shows them on screen. Pages already recorded with the same text and voice
are kept as they are.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

RATE = 24000
GAP = 0.38          # seconds of silence between blocks
VOICES = {"af_heart": ("a", "Heart"), "af_bella": ("a", "Bella"), "bf_emma": ("b", "Emma"), "bf_isabella": ("b", "Isabella")}


def fnv1a(s):
    """32-bit FNV-1a over code points; guide.js has the same function."""
    h = 0x811C9DC5
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return format(h, "08x")


FRACTIONS = {"½": "half", "¼": "a quarter", "¾": "three quarters", "⅓": "a third", "⅔": "two thirds"}
UNITS = [(r"\btbsp\b", "tablespoons"), (r"\btsp\b", "teaspoons"), (r"(\d)\s?g\b", r"\1 grams"), (r"(\d)\s?kg\b", r"\1 kilograms"),
         (r"(\d)\s?ml\b", r"\1 millilitres"), (r"(\d)\s?km\b", r"\1 kilometres"), (r"(\d)\s?cm\b", r"\1 centimetres"),
         (r"(\d)\s?am\b", r"\1 a.m."), (r"(\d)\s?pm\b", r"\1 p.m."), (r"\bvs\b\.?", "versus"), (r"\be\.g\.", "for example"),
         (r"\bi\.e\.", "that is"), (r"\betc\.", "etcetera"), (r"&", " and ")]


def speakable(text):
    """Written text → what a voice should say: number ranges, fractions, units and symbols spelled out."""
    t = re.sub(r"(\d)\s*[–-]\s*(\d)", r"\1 to \2", text)
    for f, w in FRACTIONS.items():
        t = re.sub(rf"(\d){f}", rf"\1 and {'a half' if w == 'half' else w}", t).replace(f, w)
    for pat, rep in UNITS:
        t = re.sub(pat, rep, t)
    t = t.replace("→", " ").replace("·", ", ").replace("×", " times ").replace("/", " or ")
    return re.sub(r"\s+", " ", t).strip()


def ffmpeg():
    try:
        import imageio_ffmpeg   # a static ffmpeg from pip, so CI needs no apt-get
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return "ffmpeg"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("blocks")
    ap.add_argument("out")
    ap.add_argument("--voice", default="af_heart", choices=sorted(VOICES))
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--only", default="", help="comma-separated pages, e.g. durga-puja/rituals/ashtami/")
    a = ap.parse_args()
    k, n = (int(x) for x in a.shard.split("/"))
    data = json.loads(Path(a.blocks).read_text(encoding="utf-8"))
    pages = sorted(data)
    if a.only:
        pages = [p for p in pages if p in a.only.split(",")]
    pages = [p for i, p in enumerate(pages) if i % n == k]
    lang_code, label = VOICES[a.voice]
    out = Path(a.out)
    todo = []
    for page in pages:
        d = data[page]
        h = fnv1a("\n".join(b["text"] for b in d["blocks"]))
        meta = out / page / "narration.json"
        if meta.exists():
            old = json.loads(meta.read_text(encoding="utf-8"))
            if old.get("h") == h and old.get("voice") == a.voice and old.get("v") == d["v"] and (out / page / "narration.mp3").exists():
                continue   # already recorded, unchanged
        todo.append((page, d, h))
    print(f"shard {k}/{n}: {len(pages)} pages, {len(todo)} to record", flush=True)
    if not todo:
        return
    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline
    pipe = KPipeline(lang_code=lang_code)
    gap = np.zeros(int(GAP * RATE), dtype=np.float32)
    for page, d, h in todo:
        pieces, spans, t = [], [], 0.0
        for b in d["blocks"]:
            if b["lang"] != "en":
                spans.append(None)
                continue
            chunks = [np.asarray(audio, dtype=np.float32) for _, _, audio in pipe(speakable(b["text"]), voice=a.voice, speed=1.0) if audio is not None]
            if not chunks:
                spans.append(None)
                continue
            wav = np.concatenate(chunks)
            dur = len(wav) / RATE
            spans.append([round(t, 2), round(t + dur, 2)])
            pieces += [wav, gap]
            t += dur + GAP
        dest = out / page
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            w = Path(tmp) / "n.wav"
            sf.write(w, np.concatenate(pieces), RATE)
            subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-i", str(w), "-ac", "1", "-ar", str(RATE), "-codec:a", "libmp3lame", "-b:a", "24k",
                            str(dest / "narration.mp3")], check=True)
        (dest / "narration.json").write_text(json.dumps({"v": d["v"], "h": h, "voice": a.voice, "voice_label": f"{label} (Kokoro voice)",
                                                         "duration": round(t, 1), "blocks": spans}, separators=(",", ":")), encoding="utf-8")
        print(f"  {page}: {t / 60:.1f} min, {(dest / 'narration.mp3').stat().st_size // 1024} KB", flush=True)


if __name__ == "__main__":
    sys.exit(main())
