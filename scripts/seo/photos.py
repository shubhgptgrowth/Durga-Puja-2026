"""Article photos (app/img/guide/, chosen in content/knowledge/photos.toml) → <figure>s with credits, ImageObject data and
1200×630 share cards (the picture WhatsApp, Facebook and X show for a link) with the article's title on the photo."""
import json
import os
import textwrap
from pathlib import Path

from .common import esc

ROOT = Path(__file__).resolve().parent.parent.parent
DIR = Path(os.environ.get("PPG_PHOTOS") or ROOT / "app" / "img" / "guide")   # PPG_PHOTOS: another folder, for previews and tests
FONTS = Path(__file__).resolve().parent / "fonts"
# The photo an article gets when its front matter names none
SECTION_PHOTO = {"Durga Puja": "pandal-art", "Rituals": "pushpanjali", "At home": "puja-thali", "Recipes": "bhog", "Navratri": "garba",
                 "Festivals": "diwali", "Culture": "dhaki", "Visit": "crowd"}


class Photos:
    def __init__(self, base):
        self.base = base
        f = DIR / "photos.json"
        self.items = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        toml = ROOT / "content" / "knowledge" / "photos.toml"   # captions are edited there; no re-fetch needed
        if toml.exists():
            import tomllib
            for k, v in tomllib.loads(toml.read_text(encoding="utf-8")).items():
                if k in self.items and v.get("caption"):
                    self.items[k] = {**self.items[k], "caption": v["caption"]}

    def __contains__(self, key):
        return key in self.items

    def for_article(self, a):
        """(hero key or None, [inline keys]) for an article, keeping only photos that exist."""
        hero = a.meta.get("image") or SECTION_PHOTO.get(a.section)
        inline = [k for k in a.meta.get("images", []) if k in self and k != hero]
        return (hero if hero in self else None), inline

    def credit(self, key):
        p = self.items[key]
        return (f'Photo: <a href="{esc(p["page"])}" rel="noopener">{esc(p["author"])}</a>, '
                f'{esc(p["license"])}, via Wikimedia Commons')

    def figure(self, key, up, caption=None, cls="", eager=False):
        p = self.items[key]
        cap = caption if caption is not None else p.get("caption", "")
        w, h = p["w"], p["h"]
        load = 'fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
        return (f'<figure class="photo {cls}"><img src="{up}img/guide/{key}.webp" srcset="{up}img/guide/{key}-600.webp 600w, {up}img/guide/{key}.webp {w}w" '
                f'sizes="(max-width: 760px) 100vw, 760px" width="{w}" height="{h}" alt="{esc(cap)}" {load}>'
                f'<figcaption>{esc(cap)}{" " if cap else ""}<small>{self.credit(key)}</small></figcaption></figure>')

    def thumb(self, key, up):
        if key not in self:
            return '<span class="thumb blank" aria-hidden="true"></span>'
        return f'<img class="thumb" src="{up}img/guide/{key}-600.webp" width="600" height="{round(600 * self.items[key]["h"] / self.items[key]["w"])}" alt="" loading="lazy" decoding="async">'

    def url(self, key):
        return f"{self.base}img/guide/{key}.webp"

    def ld(self, key):
        p = self.items[key]
        return {k: v for k, v in {"@type": "ImageObject", "url": self.url(key), "contentUrl": self.url(key), "width": p["w"], "height": p["h"],
                "caption": p.get("caption") or None, "creditText": p["author"], "creator": {"@type": "Person", "name": p["author"]},
                "license": p.get("license_url") or p["page"], "acquireLicensePage": p["page"],
                "copyrightNotice": f'{p["author"]}, {p["license"]}'}.items() if v}

    def share_card(self, key, title, kicker, dest):
        """1200×630 JPEG: the photo, darkened at the bottom, with the title on it. Needs Pillow; returns False without it."""
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageOps
        except ImportError:
            return False
        src = DIR / f"{key}.webp"
        if not src.exists():
            return False
        im = ImageOps.fit(Image.open(src).convert("RGB"), (1200, 630), centering=(0.5, 0.4))
        shade = Image.new("L", (1, 630))
        for y in range(630):
            shade.putpixel((0, y), int(245 * min(1.0, max(0.0, (y - 150) / 380) ** 1.1)))
        im.paste(Image.new("RGB", (1200, 630), (40, 6, 18)), (0, 0), shade.resize((1200, 630)))
        d = ImageDraw.Draw(im)
        big = ImageFont.truetype(str(FONTS / "baloo-2-latin-800-normal.woff2"), 66)
        small = ImageFont.truetype(str(FONTS / "baloo-2-latin-700-normal.woff2"), 30)
        lines = textwrap.wrap(title, 30)[:3]
        y = 630 - 60 - 74 * len(lines)
        d.rounded_rectangle((60, y - 62, 60 + d.textlength(kicker.upper(), font=small) + 32, y - 14), 22, fill=(251, 191, 36))
        d.text((76, y - 60), kicker.upper(), font=small, fill=(122, 14, 43))
        for ln in lines:
            d.text((60, y), ln, font=big, fill="white")
            y += 74
        d.text((1140, 600), "pujoparikramaguide.in", font=small, fill=(253, 230, 138), anchor="rs")
        dest.parent.mkdir(parents=True, exist_ok=True)
        im.save(dest, quality=80, optimize=True, progressive=True)
        return True
