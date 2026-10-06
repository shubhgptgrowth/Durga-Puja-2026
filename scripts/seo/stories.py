"""Photo stories: Google Web Stories (AMP) at /stories/<slug>/, from content/knowledge/stories.toml, plus a /stories/ index.

Each page is a full-screen photo from photos.toml with a heading, a line of text, the photo's credit and, where given, a
link to the guide it comes from. Google indexes Web Stories like any page and can show them in Search and Discover;
they are listed in the sitemap. Spec: https://amp.dev/documentation/components/amp-story/"""
import json
import tomllib
from pathlib import Path

from .common import NAME, esc
from .photos import DIR

ROOT = Path(__file__).resolve().parent.parent.parent
STORIES = ROOT / "content" / "knowledge" / "stories.toml"
AUDIO = ROOT / "app" / "audio"   # story music: <key>.mp3, credited in credits.json
BOILERPLATE = ("<style amp-boilerplate>body{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;"
               "-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}"
               "@-webkit-keyframes -amp-start{from{visibility:hidden}to{visibility:visible}}@-moz-keyframes -amp-start{from{visibility:hidden}to{visibility:visible}}"
               "@-ms-keyframes -amp-start{from{visibility:hidden}to{visibility:visible}}@-o-keyframes -amp-start{from{visibility:hidden}to{visibility:visible}}"
               "@keyframes -amp-start{from{visibility:hidden}to{visibility:visible}}</style><noscript><style amp-boilerplate>body{-webkit-animation:none;"
               "-moz-animation:none;-ms-animation:none;animation:none}</style></noscript>")
CSS = """@font-face{font-family:"Baloo 2";src:url(../../guide/fonts/baloo-2-latin-800-normal.woff2) format("woff2");font-weight:800;font-display:swap}
@font-face{font-family:"Literata";src:url(../../guide/fonts/literata-latin-400-normal.woff2) format("woff2");font-weight:400;font-display:swap}
amp-story{font-family:"Literata",Georgia,serif;color:#fff}
.shade{background:linear-gradient(180deg,rgba(0,0,0,0) 35%,rgba(28,4,12,.55) 58%,rgba(28,4,12,.92) 100%)}
.cover-shade{background:linear-gradient(180deg,rgba(28,4,12,.35) 0%,rgba(0,0,0,0) 30%,rgba(0,0,0,0) 45%,rgba(28,4,12,.94) 100%)}
.txt{align-content:end;padding:0 24px 92px}
.kicker{display:block;width:fit-content;justify-self:start;font:800 13px/1 "Baloo 2",sans-serif;letter-spacing:.08em;text-transform:uppercase;color:#7A0E2B;background:#FBBF24;padding:7px 10px 5px;border-radius:999px;margin:0 0 10px}
h1,h2{font-family:"Baloo 2",system-ui,sans-serif;font-weight:800;margin:0 0 8px;line-height:1.08;text-shadow:0 2px 12px rgba(0,0,0,.4)}
h1{font-size:38px}h2{font-size:30px}
p{font-size:18px;line-height:1.5;margin:0 0 10px;text-shadow:0 1px 8px rgba(0,0,0,.5)}
.dek{font-size:19px}
.credit{font:400 11px/1.35 system-ui,sans-serif;opacity:.78;margin:6px 0 0}
.brand{align-content:start;padding:22px 24px}
.brand span{font:800 15px/1 "Baloo 2",sans-serif;color:#FDE68A;letter-spacing:.02em}
.end{background:#7A0E2B;align-content:center;justify-items:center;text-align:center;padding:32px}
.end h2{color:#FDE68A;font-size:32px}
.end a.btn{display:inline-block;margin-top:14px;padding:14px 22px;border-radius:999px;background:#FBBF24;color:#7A0E2B;font:800 18px/1 "Baloo 2",sans-serif;text-decoration:none}
.end a.more{color:#fff;font:400 15px/1.4 system-ui,sans-serif;margin-top:16px}"""


class StoriesMixin:
    """Mixed into build_seo.Site (needs page(), url(), pics, by_path, out, pages, page_images)."""

    def load_stories(self):
        self.stories = tomllib.loads(STORIES.read_text(encoding="utf-8")).get("story", []) if STORIES.exists() else []
        self.story_for = {s["article"]: s for s in self.stories}

    def story_poster(self, s):
        """640×853 (3:4) poster, the image Google shows for the story; Pillow at build time, else the 600 px photo."""
        key = s["cover"]
        try:
            from PIL import Image, ImageOps
            dest = self.out / "stories" / s["slug"] / "poster.jpg"
            dest.parent.mkdir(parents=True, exist_ok=True)
            ImageOps.fit(Image.open(DIR / f"{key}.webp").convert("RGB"), (640, 853), centering=(0.5, 0.4)).save(dest, quality=80, optimize=True, progressive=True)
            return self.url(f"stories/{s['slug']}/poster.jpg"), 640, 853
        except Exception:   # no Pillow, or no photo yet
            p = self.pics.items.get(key, {"w": 600, "h": 450})
            return self.url(f"img/guide/{key}-600.webp"), 600, round(600 * p["h"] / p["w"])

    def story_pages(self):
        ph = self.pics
        for s in self.stories:
            pages = [p for p in s["pages"] if p["image"] in ph]
            if s["cover"] not in ph or len(pages) < 4:
                continue
            url = self.url(f"stories/{s['slug']}/")
            article = self.by_path.get(s["article"])
            poster, pw, phh = self.story_poster(s)

            def img(key):
                p = ph.items[key]
                return (f'<amp-img src="../../img/guide/{key}.webp" srcset="../../img/guide/{key}-600.webp 600w, ../../img/guide/{key}.webp {p["w"]}w" '
                        f'width="{p["w"]}" height="{p["h"]}" layout="fill" object-fit="cover" alt="{esc(p.get("caption", ""))}"></amp-img>')

            def credit(key):
                p = ph.items[key]
                return f'<p class="credit">{esc(p.get("caption", ""))} Photo: {esc(p["author"])}, {esc(p["license"])}, Wikimedia Commons.</p>'

            html = [f"""<amp-story-page id="cover">
<amp-story-grid-layer template="fill">{img(s["cover"])}</amp-story-grid-layer>
<amp-story-grid-layer template="fill" class="cover-shade"></amp-story-grid-layer>
<amp-story-grid-layer template="vertical" class="brand"><span>{NAME}</span></amp-story-grid-layer>
<amp-story-grid-layer template="vertical" class="txt"><h1>{esc(s["title"])}</h1><p class="dek">{esc(s["dek"])}</p>{credit(s["cover"])}</amp-story-grid-layer>
</amp-story-page>"""]
            for i, p in enumerate(pages):
                link = p.get("link")
                out = ""
                if link:
                    self.article_links.setdefault("stories", []).append(link)
                    label = self.by_path[link].label if link in self.by_path else "Read more"
                    out = (f'<amp-story-page-outlink layout="nodisplay" theme="custom" cta-accent-element="background" cta-accent-color="#FBBF24">'
                           f'<a href="../../{link}">{esc(label)}</a></amp-story-page-outlink>')
                kicker = f'<span class="kicker">{esc(p["kicker"])}</span>' if p.get("kicker") else ""
                html.append(f"""<amp-story-page id="p{i + 1}">
<amp-story-grid-layer template="fill">{img(p["image"])}</amp-story-grid-layer>
<amp-story-grid-layer template="fill" class="shade"></amp-story-grid-layer>
<amp-story-grid-layer template="vertical" class="txt">{kicker}<h2>{esc(p["heading"])}</h2><p>{esc(p["text"])}</p>{credit(p["image"])}</amp-story-grid-layer>
{out}</amp-story-page>""")
            music = s.get("music")
            credits = json.loads((AUDIO / "credits.json").read_text(encoding="utf-8")) if (AUDIO / "credits.json").exists() else {}
            if music and not ((AUDIO / f"{music}.mp3").exists() and music in credits):
                music = None
            mc = credits.get(music, {})
            music_credit = (f'<p class="credit">Music: {esc(mc.get("title", "").replace("File:", "").rsplit(".", 1)[0])}, '
                            f'{esc(mc.get("author", ""))}, {esc(mc.get("license", ""))}, Wikimedia Commons.</p>') if music else ""
            more = [x for x in self.stories if x is not s][:2]
            html.append(f"""<amp-story-page id="end">
<amp-story-grid-layer template="vertical" class="end"><h2>Read the full guide</h2>
<p>{esc(article.desc if article else s["dek"])}</p>
<a class="btn" href="../../{s["article"]}">{esc(article.label if article else "Read more")} →</a>
{"".join(f'<a class="more" href="../{x["slug"]}/">Next story: {esc(x["title"])}</a>' for x in more[:1])}
<a class="more" href="../">All photo stories</a>{music_credit}</amp-story-grid-layer>
</amp-story-page>""")
            self.article_links.setdefault("stories", []).append(s["article"])
            images = [ph.url(k) for k in dict.fromkeys([s["cover"], *(p["image"] for p in pages)])]
            ld = {"@context": "https://schema.org", "@type": "Article", "headline": s["title"][:110], "description": s["dek"], "url": url,
                  "mainEntityOfPage": url, "inLanguage": "en", "datePublished": "2026-10-06", "dateModified": self.updated,
                  "image": [poster] + images, "author": {"@type": "Organization", "name": NAME, "url": self.base},
                  "publisher": {"@type": "Organization", "name": NAME, "url": self.base,
                                "logo": {"@type": "ImageObject", "url": self.url("icons/icon-512.png"), "width": 512, "height": 512}},
                  "isPartOf": {"@type": "CollectionPage", "name": f"{NAME} photo stories", "url": self.url("stories/")}}
            doc = f"""<!doctype html>
<html ⚡ lang="en">
<head>
<meta charset="utf-8">
<title>{esc(s["title"])} | {NAME}</title>
<link rel="canonical" href="{esc(url)}">
<meta name="viewport" content="width=device-width">
<meta name="description" content="{esc(s["dek"])}">
<meta name="robots" content="index, follow, max-image-preview:large">
<meta property="og:type" content="article"><meta property="og:title" content="{esc(s["title"])}"><meta property="og:description" content="{esc(s["dek"])}">
<meta property="og:url" content="{esc(url)}"><meta property="og:image" content="{esc(poster)}"><meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../../icons/icon.svg" type="image/svg+xml">
<script async src="https://cdn.ampproject.org/v0.js"></script>
<script async custom-element="amp-story" src="https://cdn.ampproject.org/v0/amp-story-1.0.js"></script>
{BOILERPLATE}
<style amp-custom>{CSS}</style>
<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False, separators=(",", ":"))}</script>
</head>
<body>
<amp-story standalone title="{esc(s["title"])}" publisher="{NAME}" publisher-logo-src="{esc(self.url('icons/icon-192.png'))}"{f' background-audio="../../audio/{music}.mp3"' if music else ""}
 poster-portrait-src="{esc(poster)}">
{chr(10).join(html)}
</amp-story>
</body>
</html>
"""
            f = self.out / "stories" / s["slug"] / "index.html"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(doc, encoding="utf-8")
            self.pages.append((f"stories/{s['slug']}/", f"{s['title']} | {NAME}", s["dek"], 0.7))
            self.page_images[f"stories/{s['slug']}/"] = images
            self.page_modified[f"stories/{s['slug']}/"] = self.updated
            s["built"] = True

    def story_link(self, path, up):
        """The 'photo story' card shown near the top of a guide that has one."""
        s = self.story_for.get(path)
        if not s or not s.get("built"):
            return ""
        return (f"<a class='story-link' href='{up}stories/{s['slug']}/'>{self.pics.thumb(s['cover'], up)}"
                f"<span><small>▶ Photo story · {len(s['pages']) + 2} pages</small><b>{esc(s['title'])}</b></span></a>")

    def story_cards(self, up, items=None):
        items = [s for s in (items or self.stories) if s.get("built")]
        return "<ul class='story-cards'>" + "".join(
            f"<li><a href='{up}stories/{s['slug']}/'><img src='{up}img/guide/{s['cover']}-600.webp' alt='' loading='lazy' decoding='async' width='600' height='800'>"
            f"<span><small>▶ {len(s['pages']) + 2} pages</small><b>{esc(s['title'])}</b></span></a></li>" for s in items) + "</ul>"

    def stories_index(self):
        built = [s for s in self.stories if s.get("built")]
        if not built:
            return
        url = self.url("stories/")
        body = (f"<article class='post'><header class='post-head'><span class='kicker'>Photo stories</span><h1>Durga Puja in photos</h1>"
                f"<p class='dek'>{len(built)} tap-through stories: the five days, the rituals, the food, the history and the festivals around Durga Puja. "
                f"Each one takes about a minute and links to the full guide.</p></header>{self.story_cards('../')}</article>")
        ld = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "Durga Puja photo stories", "url": url, "inLanguage": "en",
               "mainEntity": {"@type": "ItemList", "numberOfItems": len(built), "itemListElement": [
                   {"@type": "ListItem", "position": i + 1, "url": self.url(f"stories/{s['slug']}/"), "name": s["title"]} for i, s in enumerate(built)]}}]
        self.page("stories/", "Durga Puja Photo Stories: Rituals, Food, History & Festivals | Pujo Parikrama",
                  f"{len(built)} Durga Puja photo stories: the five days, Maha Ashtami, Bijoya Dashami, bhog recipes, Kumartuli, Navratri and Bengal's festival season.",
                  body, ld=ld, crumbs=(("Photo stories", "stories/"),), priority=0.8, app_link=None, note="",
                  images=[self.pics.url(s["cover"]) for s in built], og_image=self.pics.url(built[0]["cover"]))
