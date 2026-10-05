"""Wave 1 posts and stories (marketing/posts4/spec4.json) in the real-photo look of the carousels.

    python -m marketing.posts --out <dir>          # downloads the photos, writes <dir>/posts.json + <id>/caption.txt
    SPEC=posts.json node marketing/carousels.mjs <dir>   # renders <dir>/<id>/slide-NN.jpg

Same words as before, new layouts: every slide is a full-bleed photograph (Wikimedia Commons, or a photoreal AI image
where no real photo of the moment exists: the 90s memories, an adda) with the type set straight on it. Needs network.
"""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

from .photos import ROOT, UA, Library

SPEC = ROOT / "marketing" / "posts4" / "spec4.json"
HANDLE = "@pujoparikrama.guide"
DEFAULT = {"cta": "p186", "list": "p088", "bingo": "p087", "versus": "p107"}


def convert(post):
    """spec4 slide → carousels.mjs slide (keeps every line of copy)."""
    out, n = [], len(post["slides"])
    words = [s for s in post["slides"] if s["t"] == "word"]
    for i, s in enumerate(post["slides"]):
        t, img = s["t"], s.get("img") or (s.get("grid") or [None])[0]
        d = {"py": s.get("cy", 0.4)}
        if t == "cover":
            d.update(t="cover", kicker=s.get("kicker", ""), title=s["bn"], accent=s.get("bn2", ""), sub=s.get("en", ""))
        elif t == "word":
            d.update(t="word", kicker=f"{words.index(s) + 1}/{len(words)} · {s['tr']}", bn=s["bn"], body=s["en"])
        elif t == "pat":
            d.update(t="quote", kicker=f"নম্বর {s['num']}", bn=s["bn"], title=s["en"])
        elif t in ("prompt", "story"):
            d.update(t="prompt", title=s["bn"] + (" …" if s.get("blank") else ""), body=s["en"],
                     hint=s.get("hint", ""))
        elif t == "versus":
            d.update(t="split", title=s["bn"], sub=s["en"], labels=[s["lbl"], s["rbl"]], sides=[s["left"], s["right"]])
            img = None
        elif t == "list":
            d.update(t="cols", title=s["bn"], sub=s["en"], cols=s["cols"])
        elif t == "bingo":
            d.update(t="bingo", title=s["bn"], foot=s["en"], cells=[{"bn": a, "en": b} for a, b in s["cells"]])
        elif t == "cta":
            d.update(t="cta", kicker=s.get("tag", ""), big=s["bn"], mid=s["en"], btn="Plan your pujo free · link in bio")
        d["img"] = img or DEFAULT.get(t) or "p087"
        if t == "versus":
            d.pop("img")
        out.append(d)
    return out


def fetch_art(url, out_dir):
    name = "ai-" + hashlib.sha1(url.encode()).hexdigest()[:12] + Path(url.split("?")[0]).suffix
    dest = Path(out_dir) / "_photos" / name
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            dest.write_bytes(r.read())
    return f"_photos/{name}", "AI-generated image"


def build(out, spec_path=SPEC):
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    g = json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
    lib = Library(g)
    pool = {}
    for row in (ROOT / "marketing" / "reels" / "photos3.tsv").read_text(encoding="utf-8").splitlines():
        parts = row.split("\t")
        if len(parts) >= 2:
            pool[parts[0]] = parts[1]
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)

    def photo(ref):
        if ref.startswith("k"):
            return fetch_art(spec["art"][ref], out)
        return lib.fetch({"file": pool[ref]}, out) or (None, None)

    posts = []
    for p in spec["posts"]:
        slides = convert(p)
        credits = []
        for s in slides:
            refs = s.pop("sides", None) or [s.pop("img")]
            got = [photo(r) for r in refs]
            if s["t"] == "split":
                s["photos"] = [x[0] for x in got]
                s["credit"] = " | ".join(x[1] for x in got if x[1])
            else:
                s["photo"], s["credit"] = got[0]
            for x in got:
                c = (x[1] or "").replace(" · Wikimedia Commons", "")
                if c and c not in credits:
                    credits.append(c)
        size = [1080, 1920] if p["size"] == "story" else [1080, 1350]
        c = p.get("caption") or {}
        cap = "\n\n".join(x for x in (c.get("bn"), c.get("en"), c.get("tags")) if x)
        real = [x for x in credits if x != "AI-generated image"]
        if real:
            cap += f"\n\n📷 Photos: {'; '.join(real)} (Wikimedia Commons)"
        if "AI-generated image" in credits:
            cap += "\n🤖 Some images are AI-generated."
        d = out / p["id"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "caption.txt").write_text(cap.strip() + "\n", encoding="utf-8")
        posts.append({"id": p["id"], "kind": p["size"], "size": size, "slides": slides, "caption": cap.strip(),
                      "hints": [s.get("hint") for s in slides if s.get("hint")]})
    (out / "posts.json").write_text(json.dumps({"handle": HANDLE, "posts": posts}, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    return posts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    ps = build(a.out)
    print(f"{len(ps)} posts, {sum(len(p['slides']) for p in ps)} slides → {a.out}")


if __name__ == "__main__":
    main()
