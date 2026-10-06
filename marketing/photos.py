"""Real photos for the static posts: every carousel slide, post and story gets a Wikimedia Commons photograph.

    from marketing import photos
    lib = photos.Library(guide)          # pandal, food, dish and general pujo photos, all CC-licensed
    lib.dress(slides, out_dir)           # sets slide["photo"] / item["thumb"] and downloads the files

A slide about a pandal or eatery shows that place; a slide about a ritual, a word or a tip gets the general photo whose
label best matches its text (dhunuchi, sindoor khela, Kumartuli, dhak, bhog…). No photo repeats inside one post. Each
photo carries its credit line (author · licence · Wikimedia Commons), which the renderers print on the slide.
Downloads need commons.wikimedia.org; offline, slides keep no photo and the renderers fall back to a dark frame.
"""
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "PujoParikramaBot/1.0 (https://github.com/shubhgptgrowth/Durga-Puja-2026; social posts)"}
POOL_TSV = ROOT / "marketing" / "reels" / "photos3.tsv"

# general photos by topic: a slide whose text matches the left side prefers photos whose label matches the right
TOPICS = [
    (r"dhunuchi|dhunachi|smoke|aarti|arati|sandhi|ধুনুচি|আরতি", r"dhunuchi|navami|saptami"),
    (r"sindoor|sindur|boron|baran|bijoya|dashami|সিঁদুর|দশমী|বিজয়া", r"sindoor|boron|bijoya|dashami"),
    (r"visarjan|immersion|bisarjan|ganga|ghat|বিসর্জন", r"visarjan|kumartuli ghat|dashami"),
    (r"kumartuli|idol|potter|artisan|chokkhu|কুমোরটুলি|প্রতিমা", r"kumartuli|idol"),
    (r"dhak|dhaki|drum|ঢাক", r"dhaki|dhak"),
    (r"bhog|khichuri|food|eat|sweet|phuchka|biryani|cutlet|kabiraji|refuel|ভোগ|খাওয়া", r"bhog|raj bhog"),
    (r"bodhon|mahalaya|shashthi|bodhan|বোধন|মহালয়া", r"bodhon"),
    (r"nabapatrika|kola bou|kolabou|saptami|নবপত্রিকা", r"nabapatrika|kola bou"),
    (r"light|night|late|midnight|all.?nighter|রাত", r"lights|navami|nalin|festivities"),
    (r"crowd|queue|rush|peak|hack|ভিড়|লাইন", r"crowd|festivities|nalin|saptami"),
    (r"carnival|red road", r"carnival"),
]


def _get(url, tries=3):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                raise
            time.sleep(2 * (k + 1))
        except Exception:
            time.sleep(2 * (k + 1))
    raise OSError(f"could not fetch {url}")


def bigger(src, width):
    """A Commons thumbnail URL at another standard width (960px- → 1280px-)."""
    return re.sub(r"/\d+px-", f"/{width}px-", src.split("?")[0], count=1)


class Library:
    def __init__(self, guide, pool_tsv=POOL_TSV):
        self.place = {}      # lower-case name → [photo]
        for p in guide["pandals"]:
            if p.get("photos"):
                for key in {p["name"], p["name"].split(" (")[0], p["id"]}:
                    self.place[key.lower()] = p["photos"]
        for f in guide["food"]:
            if f.get("photos"):
                for key in {f["name"], f["name"].split(" (")[0], f["id"]}:
                    self.place[key.lower()] = f["photos"]
        self.dish = {k.lower(): [v] for k, v in (guide.get("dish_photos") or {}).items()}
        self.general = []    # {title, label} from the curated list the reels use
        if Path(pool_tsv).exists():
            for row in Path(pool_tsv).read_text(encoding="utf-8").splitlines():
                parts = row.split("\t")
                if len(parts) >= 3:
                    self.general.append({"file": parts[1], "label": parts[2]})
        self.heroes = [ph for p in guide["pandals"] for ph in (p.get("photos") or [])[:1]]
        self._meta = {}

    # ------------------------------------------------------------ choosing
    def for_name(self, name):
        n = (name or "").lower().split(" (")[0].strip()
        return self.place.get(n) or self.dish.get(n) or []

    def topical(self, text):
        """General photos ordered by how well their label fits the text."""
        text = (text or "").lower()
        want = [lab for pat, lab in TOPICS if re.search(rf"(?<![a-z])(?:{pat})", text)]
        def score(g):
            return -sum(1 for lab in want if re.search(lab, g["label"].lower()))
        return sorted(self.general, key=score) if want else []

    # ------------------------------------------------------------ fetching
    def commons_meta(self, file):
        """File title → {src, author, license, page} via the Commons API (cached)."""
        if file not in self._meta:
            u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
                "action": "query", "format": "json", "titles": "File:" + file, "prop": "imageinfo",
                "iiprop": "url|extmetadata|size", "iiurlwidth": 1280})
            try:
                page = next(iter(json.loads(_get(u))["query"]["pages"].values()))
                ii = page["imageinfo"][0]
                m = ii.get("extmetadata", {})
                clean = lambda k: re.sub(r"\s+", " ", re.sub("<[^>]+>", "", m.get(k, {}).get("value", ""))).strip()
                self._meta[file] = {"src": ii.get("thumburl") or ii["url"], "author": clean("Artist")[:60],
                                    "license": clean("LicenseShortName"), "page": ii.get("descriptionurl"), "w": ii.get("width")}
            except Exception:
                self._meta[file] = None
        return self._meta[file]

    def fetch(self, ph, out_dir):
        """Downloads one photo into out_dir/_photos/ → (relative path, credit) or None."""
        if "file" in ph:
            meta = self.commons_meta(ph["file"])
            if not meta:
                return None
            ph = dict(ph, **meta)
        name = hashlib.sha1(ph["src"].encode()).hexdigest()[:12] + ".jpg"
        dest = Path(out_dir) / "_photos" / name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = None
            for w in (1920, 1280, None):
                try:
                    data = _get(bigger(ph["src"], w) if w else ph["src"])
                    break
                except Exception:
                    continue
            if not data:
                return None
            dest.write_bytes(data)
        credit = " · ".join(x for x in (ph.get("author") or "Unknown", ph.get("license") or "", "Wikimedia Commons") if x)
        return f"_photos/{name}", credit

    # ------------------------------------------------------------ dressing slides
    def dress(self, slides, out_dir, seed=0, fetch=True):
        """Gives every slide a hero photo and every list item with a known place a thumbnail. No repeats in a post."""
        used = set()

        def key(ph):
            return ph.get("src") or ph.get("file")

        def take(cands):
            for ph in cands:
                if key(ph) not in used:
                    used.add(key(ph))
                    return ph
            return None

        def attach(target, field, ph, field_credit):
            if not ph:
                return
            if fetch:
                got = self.fetch(ph, out_dir)
                if not got:
                    return
                target[field], target[field_credit] = got
            else:
                target[field], target[field_credit] = key(ph), ""

        k = seed
        for s in slides:
            items = s.get("items") or []
            names = [it.get("name", "") for it in items if isinstance(it, dict)]
            text = " ".join(str(s.get(x, "")) for x in ("kicker", "title", "body", "sub", "bn", "accent"))
            text += " " + " ".join(str(it.get("name", "")) + " " + str(it.get("meta", "")) for it in items if isinstance(it, dict))
            cands = [ph for n in names + [s.get("place", "")] for ph in self.for_name(n)]
            cands += self.topical(text)
            k += 1
            rot = self.heroes[k % len(self.heroes):] + self.heroes[:k % len(self.heroes)] if self.heroes else []
            hero = take(cands + rot + self.general)
            attach(s, "photo", hero, "credit")
            has_thumbs = sum(1 for it in items if isinstance(it, dict) and self.for_name(it.get("name", ""))) >= len(items) / 2
            for it in items:
                if isinstance(it, dict) and it.get("name"):
                    own = self.for_name(it["name"])
                    ph = next((p for p in own if key(p) != key(hero or {})), own[0] if own else None)
                    if not ph and has_thumbs:  # keep the rows consistent: a fitting pujo photo for a place we lack
                        ph = take(self.topical(it["name"] + " " + str(it.get("meta", ""))) + rot[1:] + self.general)
                    if ph:
                        attach(it, "thumb", ph, "thumb_credit")
        return slides
