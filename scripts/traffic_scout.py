"""Kolkata Traffic Police advisories: find puja-related notices on the official site.

  python scripts/traffic_scout.py scout   # print what the site exposes (pages, notice links)
  python scripts/traffic_scout.py fetch   # write app/data/traffic.json with the latest relevant notices

Runs in CI (the dev sandbox can't reach the site). Only links to the police's own documents; never rewrites them."""
import json, re, sys, urllib.parse, urllib.request, datetime
from html.parser import HTMLParser
from pathlib import Path

BASE = "https://kolkatatrafficpolice.gov.in/"
PAGES = ["", "notification.php", "notifications.php", "notice.php", "trafficadvisory.php", "advisory.php", "press.php", "news.php", "whatsnew.php"]
UA = {"User-Agent": "Mozilla/5.0 (compatible; PujoParikrama/1.0; +https://shubhgptgrowth.github.io/Durga-Puja-2026/)"}
RELEVANT = re.compile(r"puja|pujo|durga|mahalaya|immersion|bisarjan|visarjan|festiv|carnival|traffic (?:arrangement|restriction|regulation)|diversion|advisory|notification", re.I)

class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links = []; self._href = None; self._text = []
    def handle_starttag(self, tag, attrs):
        if tag == "a": self._href = dict(attrs).get("href"); self._text = []
    def handle_data(self, d):
        if self._href is not None: self._text.append(d)
    def handle_endtag(self, tag):
        if tag == "a" and self._href:
            self.links.append((self._href, " ".join("".join(self._text).split()))); self._href = None

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read()

def crawl():
    seen, out = set(), []
    for p in PAGES:
        url = urllib.parse.urljoin(BASE, p)
        try:
            html = get(url).decode("utf-8", "replace")
        except Exception as e:
            print(f"page {url}: {e}"); continue
        print(f"page {url}: {len(html)} bytes")
        lp = Links(); lp.feed(html)
        for href, text in lp.links:
            full = urllib.parse.urljoin(url, href)
            if full in seen: continue
            seen.add(full)
            if RELEVANT.search(text + " " + href) or full.lower().endswith(".pdf"):
                out.append({"title": text or Path(urllib.parse.urlparse(full).path).name, "url": full, "page": url})
    return out

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "scout"
    items = crawl()
    for it in items: print(f"  {it['title'][:90]} | {it['url']}")
    if mode == "fetch":
        puja = [i for i in items if re.search(r"puja|pujo|durga|mahalaya|immersion|festiv|carnival", i["title"] + i["url"], re.I)]
        Path("app/data/traffic.json").write_text(json.dumps({"source": BASE, "checked": datetime.datetime.utcnow().isoformat(timespec="minutes") + "Z", "notices": puja[:12]}, ensure_ascii=False, indent=1))
        print(f"wrote {len(puja)} puja notices")
