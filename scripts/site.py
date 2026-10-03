"""The app's public address lives in site.json. Everything that prints or links it reads from there:
the Open Graph tags in app/index.html, the content kit (marketing/kit.py, render.mjs), QR posters and
the deploy checks.

    python scripts/site.py show
    python scripts/site.py set https://pujoparikrama.in/   # update site.json and app/index.html
    python scripts/site.py check                           # non-zero if they disagree (run by the tests)
"""
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
SITE_JSON, INDEX = ROOT / "site.json", ROOT / "app" / "index.html"
OG = re.compile(r'(<meta property="og:(?:url|image)" content=")([^"]*?)((?:icons/og\.png)?")')


def load():
    return json.loads(SITE_JSON.read_text(encoding="utf-8"))


def url():
    return load()["url"]


def display(u=None):
    """'pujoparikrama.in' or 'shubhgptgrowth.github.io/Durga-Puja-2026', for printing on cards."""
    p = urlparse(u or url())
    return (p.netloc + p.path).rstrip("/")


def normalise(u):
    p = urlparse(u.strip())
    if p.scheme != "https" or not p.netloc:
        raise SystemExit(f"need an https URL, got {u!r}")
    return f"https://{p.netloc}{p.path if p.path.endswith('/') else p.path + '/'}"


def og_urls():
    return [m.group(2) for m in OG.finditer(INDEX.read_text(encoding="utf-8"))]


def set_url(u):
    u = normalise(u)
    data = load(); data["url"] = u
    SITE_JSON.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    html = OG.sub(lambda m: m.group(1) + u + m.group(3), INDEX.read_text(encoding="utf-8"))
    INDEX.write_text(html, encoding="utf-8")
    print(f"site: {u}\nNext: commit, push, then follow docs/product/HOSTING.md to point the domain.")


def check():
    bad = [x for x in og_urls() if x != url()]
    if bad or len(og_urls()) != 2:
        raise SystemExit(f"app/index.html Open Graph tags {og_urls()} don't match site.json {url()}; run: python scripts/site.py set {url()}")
    print(f"site: {url()} (index.html in sync)")


if __name__ == "__main__":
    cmd = sys.argv[1:2] or ["show"]
    if cmd == ["set"] and len(sys.argv) == 3:
        set_url(sys.argv[2])
    elif cmd == ["check"]:
        check()
    elif cmd == ["show"]:
        print(json.dumps(load(), indent=2))
    else:
        raise SystemExit(__doc__)
