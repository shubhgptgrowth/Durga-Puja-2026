"""Knowledge articles (content/knowledge/**/*.md) → pages with Article / HowTo / FAQPage / DefinedTermSet data.

Each article also gets a plain Markdown copy next to it (index.md), linked from llms.txt, for AI crawlers."""
import re
import tomllib
from urllib.parse import quote
from pathlib import Path

from .common import NAME, esc, nice_date
from .markdown import render
from .photos import Photos

ISO = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?$")


def minutes(iso):
    m = ISO.match(iso or "")
    return (int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) if m else 0


def human(mins):
    return f"{mins // 60} h {mins % 60} min".replace(" 0 min", "") if mins >= 60 else f"{mins} min"


def share_text(title, summary, url):
    """What a WhatsApp share says: the title, the first sentence of the answer, the link."""
    first = re.split(r"(?<=[.!?])\s", summary, maxsplit=1)[0]
    return f"{title}\n\n{first if len(first) <= 200 else first[:197] + '…'}\n\n{url}"


def share_bar(text, cls=""):
    return (f'<div class="share {cls}" aria-label="Share"><a class="sb wa" href="https://wa.me/?text={quote(text)}" rel="noopener" data-wa>'
            '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5-1.3A10 10 0 1 0 12 2Zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-2.9-.2-.3A8.2 8.2 0 1 1 12 20.2Zm4.5-6.1c-.2-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1l-.8 1c-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.3-2.9c-.3-.4.2-.4.7-1.3.1-.2 0-.3 0-.4l-.8-1.8c-.2-.5-.4-.4-.6-.4h-.5a1 1 0 0 0-.7.3 3 3 0 0 0-.9 2.2 5.2 5.2 0 0 0 1.1 2.8 11.9 11.9 0 0 0 4.6 4c1.7.7 2.4.8 3.2.7.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2-.1-.1-.3-.2-.5-.3Z"/></svg> <span>WhatsApp</span></a>'
            '<button class="sb" type="button" data-share="native">Share</button><button class="sb" type="button" data-share="copy">Copy link</button></div>')


ROOT = Path(__file__).resolve().parent.parent.parent
CONTENT = ROOT / "content" / "knowledge"
SECTIONS = ["Durga Puja", "Rituals", "At home", "Recipes", "Navratri", "Festivals", "Culture", "Visit"]
DURGA_PUJA = {"@type": "Thing", "name": "Durga Puja", "sameAs": ["https://en.wikipedia.org/wiki/Durga_Puja", "https://www.wikidata.org/wiki/Q1361960"]}
PUBLISHED = "2026-10-06"


class Article:
    def __init__(self, file):
        raw = file.read_text(encoding="utf-8")
        m = re.match(r"^\+\+\+\n(.*?)\n\+\+\+\n(.*)$", raw, re.S)
        if not m:
            raise ValueError(f"{file}: missing +++ front matter")
        self.meta, self.body = tomllib.loads(m.group(1)), m.group(2)
        rel = file.relative_to(CONTENT).with_suffix("")
        self.path = (str(rel.parent) if rel.name == "index" else str(rel)).replace("\\", "/").strip(".") + "/"
        self.path = self.path.lstrip("/")
        self.file = file
        for k in ("title", "description", "h1", "summary"):
            if not self.meta.get(k):
                raise ValueError(f"{file}: front matter needs '{k}'")
        g = self.meta.get
        self.title, self.desc, self.h1, self.summary = g("title"), g("description"), g("h1"), " ".join(g("summary").split())
        self.type, self.section, self.order = g("type", "Article"), g("section", "Durga Puja"), g("order", 100)
        self.published, self.modified = g("published", PUBLISHED), g("updated", g("published", PUBLISHED))
        self.is_hub = rel.name == "index"

    @property
    def label(self):
        """Short name for lists: the h1 up to its colon."""
        return self.h1.split(":")[0].strip()


class KnowledgeMixin:
    """Mixed into build_seo.Site, which provides page(), url(), pandal, out, pages and full."""

    def load_articles(self):
        files = sorted(f for f in CONTENT.rglob("*.md") if f.name != "README.md") if CONTENT.exists() else []
        self.articles = [Article(f) for f in files]
        self.by_path = {a.path: a for a in self.articles}
        self.article_links = {}   # path -> internal links found in it, checked after the build
        self.pics = Photos(self.base)

    def section_list(self, section, up, exclude=None):
        items = sorted((a for a in self.articles if a.section == section and a is not exclude and a.path != "durga-puja/"),
                       key=lambda a: (a.order, a.path))
        return self.cards(items, up)

    def cards(self, items, up, cls="cards pics"):
        """Article cards with their photo, title and a two-line description."""
        def card(x):
            hero, _ = self.pics.for_article(x)
            return (f"<li><a href='{up}{x.path}'>{self.pics.thumb(hero, up)}<span class='ct'><small>{esc(x.section)}</small>"
                    f"<b>{esc(x.label)}</b><span>{esc(x.desc)}</span></span></a></li>")
        return f"<ul class='{cls}'>" + "".join(card(x) for x in items) + "</ul>" if items else ""

    def hub_listing(self, a, up):
        if a.path == "durga-puja/":   # the main hub: everything, by section
            return "".join(f"<h2 id='{s.lower().replace(' ', '-')}'>{esc(s)}</h2>{self.section_list(s, up)}" for s in SECTIONS if self.section_list(s, up))
        return f"<h2 id='in-this-section'>In this section</h2>{self.section_list(a.section, up, exclude=a)}"

    def article_page(self, a):
        up = "../" * a.path.count("/")
        url = self.url(a.path)
        ph = self.pics
        hero, inline = ph.for_article(a)
        placed = set()   # photos the body places itself with ![caption](photo:key)
        r = render(a.body, up, figure=lambda k, c: (placed.add(k) or ph.figure(k, up, c or None)) if k in ph else "")
        self.article_links[a.path] = list(r.links) + [p for p in a.meta.get("related", [])]
        faq = a.meta.get("faq", [])
        toc = ("<details class='toc'><summary>In this article <span>" + f"{len(r.toc)} sections</span></summary><ol>"
               + "".join(f"<li><a href='#{i}'>{esc(t)}</a></li>" for i, t in r.toc)
               + ("<li><a href='#faq'>Questions people ask</a></li>" if faq else "") + "</ol></details>") if len(r.toc) >= 3 else ""
        howto = ""
        steps = a.meta.get("steps", [])
        recipe = a.type == "Recipe"
        step_list = "<ol class='steps'>" + "".join(f"<li><b>{esc(st['name'])}</b><p>{esc(st['text'])}</p></li>" for st in steps) + "</ol>"
        if recipe:
            g = a.meta.get
            prep, cook = minutes(g("prep_time")), minutes(g("cook_time"))
            facts = [("🍽", "Serves", g("recipe_yield")), ("🔪", "Prep", human(prep) if prep else None), ("🔥", "Cook", human(cook) if cook else None),
                     ("⏱", "Total", human(prep + cook) if prep + cook else None), ("🌿", "Diet", g("diet") or None)]
            howto = ("<dl class='recipe-facts'>" + "".join(f"<div><dt><span aria-hidden='true'>{i}</span> {k}</dt><dd>{esc(v)}</dd></div>" for i, k, v in facts if v) + "</dl>"
                     + "<section class='box ingredients'><h2 id='ingredients'>Ingredients</h2><p class='hint'>Tick them off as you go; ticks stay on this phone.</p><ul class='checklist'>"
                     + "".join(f'<li><label><input type="checkbox" data-k="i{n}"> {esc(x)}</label></li>' for n, x in enumerate(g("ingredients", [])))
                     + f"</ul></section><h2 id='method'>Method</h2>{step_list}")
        elif steps:
            sup = a.meta.get("supplies", [])
            howto = (("<section class='box'><h2 id='what-you-need'>What you need</h2><ul class='checklist'>"
                      + "".join(f'<li><label><input type="checkbox" data-k="s{n}"> {esc(x)}</label></li>' for n, x in enumerate(sup)) + "</ul></section>" if sup else "")
                     + f"<h2 id='steps'>Step by step</h2>{step_list}")
        terms = a.meta.get("terms", [])
        glossary = ("<dl class='glossary'>" + "".join(f"<dt id='{re.sub(r'[^a-z0-9]+', '-', t['term'].lower()).strip('-')}'>{esc(t['term'])}"
                                                       f"{(' <span lang=bn>' + esc(t['alt']) + '</span>') if t.get('alt') else ''}</dt><dd>{esc(t['definition'])}</dd>"
                                                       for t in sorted(terms, key=lambda t: t['term'].lower())) + "</dl>") if terms else ""
        places = [p for p in a.meta.get("places", []) if p in self.pandal]
        places_html = ("<h2 id='see-it-in-kolkata'>See it in Kolkata</h2><ul class='cards places'>" + "".join(
            f"<li><a href='{up}guide/pandals/{p}/'><b>📍 {esc(self.pandal[p]['name'])}</b><span>{esc(self.pandal[p]['highlight'])}</span></a></li>" for p in places) + "</ul>") if places else ""
        faq_ld = self.faq([(f["q"], esc(f["a"])) for f in faq])[1] if faq else None
        faq_html = ("<section class='faq'><h2 id='faq'>Questions people ask</h2>" + "".join(
            f"<details{' open' if n == 0 else ''}><summary>{esc(f['q'])}</summary><p>{esc(f['a'])}</p></details>" for n, f in enumerate(faq)) + "</section>") if faq else ""
        related = [self.by_path[p] for p in a.meta.get("related", []) if p in self.by_path]
        related_html = f"<h2 id='related'>Read next</h2>{self.cards(related, up)}" if related else ""
        sources = a.meta.get("sources", [])
        sources_html = ("<h2 id='sources'>Sources and further reading</h2><ul class='sources'>" + "".join(f"<li><a href='{esc(s['url'])}' rel='noopener'>{esc(s['name'])}</a></li>" for s in sources) + "</ul>") if sources else ""
        hub = self.hub_listing(a, up) if a.is_hub else ""
        words = len(r.text.split()) + len(a.summary.split())
        mins = max(1, round(words / 220))
        hub_path = next((x.path for x in self.articles if x.is_hub and x.section == a.section and x is not a), None)
        kicker = (f"<a class='kicker' href='{up}{hub_path}'>{esc(a.section)}</a>" if hub_path else f"<span class='kicker'>{esc(a.section)}</span>")
        byline = (f"<p class='byline'><img src='{up}icons/icon-192.png' alt='' width='28' height='28'><span><b>{NAME} team</b>"
                  f"<span>{mins} min read · Updated <time datetime='{a.modified}'>{nice_date(a.modified, True).split(' (')[0]}</time></span></span></p>")
        text = share_text(a.h1, a.summary, url)

        # Photos and a "keep reading" card between sections, so long pages read in stages
        prose = r.html
        if a.type != "Glossary" and not a.is_hub:
            chunks = re.split(r"(?=<h2 )", prose)
            breaks = {}
            n_h2 = len(chunks) - 1
            spare = [k for k in inline if k not in placed]
            for i, key in enumerate(spare):
                at = round((i + 1) * n_h2 / (len(spare) + 1)) or 1
                while at in breaks and at < n_h2:
                    at += 1
                if 1 <= at <= n_h2 and at not in breaks:
                    breaks[at] = ph.figure(key, up)
            if related and n_h2 >= 4:
                mid = n_h2 // 2 + 1
                while mid in breaks and mid < n_h2:
                    mid += 1
                x = related[0]
                xh, _ = ph.for_article(x)
                breaks.setdefault(mid, f"<a class='also' href='{up}{x.path}'>{ph.thumb(xh, up)}<span><small>Also read</small><b>{esc(x.label)}</b></span></a>")
            prose = "".join((breaks.get(i, "") + c) for i, c in enumerate(chunks))
        hero_html = ph.figure(hero, up, cls="hero", eager=True) if hero else ""
        about = (f"<aside class='about-box'><b>About this guide</b><p>{NAME} is an independent, free guide to Durga Puja. "
                 f"Articles are checked against the sources listed above, say where traditions differ, and are corrected quickly: "
                 f"<a href='{up}contact/'>tell us</a> if you spot one. <a href='{up}about/'>More about us</a>.</p></aside>")
        share_end = (f"<section class='share-end'><p class='se-t'>Found this useful?</p><p>Send it to the family group before the pujo; "
                     f"it takes {mins} minutes to read and answers the questions everyone asks.</p>{share_bar(text, 'end')}</section>")
        body = f"""<article class="post{' hub' if a.is_hub else ''}">
<header class="post-head">{kicker}
<h1>{esc(a.h1)}</h1>
{byline}
</header>
{hero_html}
<section class="tldr"><b>In short</b><p>{esc(a.summary)}</p></section>
{share_bar(text)}
{toc}
{howto}
<div class="prose">{prose}</div>
{glossary}
{hub}
{places_html}
{faq_html}
{share_end}
{related_html}
{sources_html}
{about}
</article>"""
        org = {"@type": "Organization", "name": NAME, "url": self.base, "logo": {"@type": "ImageObject", "url": self.url("icons/icon-512.png")}}
        images = list(dict.fromkeys(k for k in [hero, *inline, *sorted(placed)] if k))
        card = None
        if hero and ph.share_card(hero, a.label, a.section, self.out / "og" / (a.path.strip("/").replace("/", "--") or "home") / "card.jpg"):
            card = self.url("og/" + (a.path.strip("/").replace("/", "--") or "home") + "/card.jpg")
        self.og_image = card or (ph.url(hero) if hero else None)
        main = {"@context": "https://schema.org", "@type": "Recipe" if recipe else "HowTo" if steps else "Article", "@id": url + "#main", "headline": a.h1[:110], "name": a.h1,
                "description": a.desc, "url": url, "mainEntityOfPage": url, "inLanguage": "en", "datePublished": a.published, "dateModified": a.modified,
                "author": org, "publisher": org, "about": DURGA_PUJA,
                "image": [ph.ld(k) for k in images] or self.url("icons/og.png"), "isAccessibleForFree": True,
                "keywords": ", ".join(a.meta.get("keywords", [])), "wordCount": len(r.text.split())}
        if recipe:
            g = a.meta.get
            prep, cook = minutes(g("prep_time")), minutes(g("cook_time"))
            main.update({"recipeYield": g("recipe_yield"), "prepTime": g("prep_time"), "cookTime": g("cook_time"),
                         "totalTime": f"PT{prep + cook}M" if prep + cook else None, "recipeCategory": g("recipe_category"),
                         "recipeCuisine": g("recipe_cuisine", "Bengali"), "recipeIngredient": g("ingredients", []),
                         "recipeInstructions": [{"@type": "HowToStep", "position": i + 1, "name": st["name"], "text": st["text"], "url": f"{url}#method"} for i, st in enumerate(steps)]})
            if g("diet") in ("Vegetarian", "Vegan"):
                main["suitableForDiet"] = f"https://schema.org/{g('diet')}Diet"
            for k in ("headline", "wordCount", "isAccessibleForFree", "mainEntityOfPage", "about"):
                main.pop(k, None)
            main = {k: v for k, v in main.items() if v is not None}
        elif steps:
            main.update({"totalTime": a.meta.get("total_time"), "supply": [{"@type": "HowToSupply", "name": x} for x in a.meta.get("supplies", [])],
                         "step": [{"@type": "HowToStep", "position": i + 1, "name": s["name"], "text": s["text"]} for i, s in enumerate(steps)]})
            main = {k: v for k, v in main.items() if v is not None}
        if sources:
            main["citation"] = [s["url"] for s in sources]
        ld = [main] + ([faq_ld] if faq_ld else [])
        if terms:
            ld.append({"@context": "https://schema.org", "@type": "DefinedTermSet", "@id": url + "#terms", "name": a.h1, "url": url,
                       "hasDefinedTerm": [{"@type": "DefinedTerm", "name": t["term"], **({"alternateName": t["alt"]} if t.get("alt") else {}),
                                           "description": t["definition"], "inDefinedTermSet": url + "#terms"} for t in terms]})
        crumbs = self.article_crumbs(a)
        self.page(a.path, a.title, a.desc, body, ld=ld, crumbs=crumbs, priority=0.9 if a.is_hub else 0.8, summary=a.summary, app_link=None,
                  note=f"Published {nice_date(a.published, True)}, last updated <time datetime='{a.modified}'>{nice_date(a.modified, True)}</time>, by the {NAME} team. "
                       "Practices vary by family, region and panjika; check with your purohit or local almanac for exact timings.",
                  modified=a.modified, head_extra='<link rel="alternate" type="text/markdown" href="index.md" title="Markdown">',
                  images=[ph.url(k) for k in images], og_image=self.og_image, og_alt=ph.items[hero].get("caption", "") if hero else "")
        # A plain-text copy for AI crawlers (linked from llms.txt)
        md = f"# {a.h1}\n\n> {a.summary}\n\nSource: {url} (updated {a.modified})\n\n{a.body.strip()}\n"
        if recipe:
            md += "\n## Ingredients\n\n" + "\n".join(f"- {x}" for x in a.meta.get("ingredients", [])) + "\n\n## Method\n\n" + "\n".join(
                f"{i + 1}. **{st['name']}**: {st['text']}" for i, st in enumerate(steps)) + "\n"
        elif steps:
            md += "\n## Steps\n\n" + "\n".join(f"{i + 1}. **{st['name']}**: {st['text']}" for i, st in enumerate(steps)) + "\n"
        if faq:
            md += "\n## Frequently asked questions\n\n" + "\n\n".join(f"**{f['q']}**\n{f['a']}" for f in faq) + "\n"
        if terms:
            md += "\n## Terms\n\n" + "\n".join(f"- **{t['term']}**{(' (' + t['alt'] + ')') if t.get('alt') else ''}: {t['definition']}" for t in terms) + "\n"
        (self.out / a.path / "index.md").write_text(md, encoding="utf-8")
        self.full.append(f"## {a.h1}\n{a.summary}\nPage: {url}\n")

    def article_crumbs(self, a):
        crumbs, parts = [], a.path.strip("/").split("/")
        for i in range(1, len(parts) + 1):
            p = "/".join(parts[:i]) + "/"
            if p in self.by_path:
                crumbs.append((self.by_path[p].label, p))
        return tuple(crumbs) or ((a.label, a.path),)

    def check_article_links(self):
        """Every internal link in an article must point at a page this build wrote (or a file in app/)."""
        bad = []
        for src, links in self.article_links.items():
            for p in links:
                p = p.split("#")[0]
                if p in ("",) or (self.out / p / "index.html").exists() or (self.out / p).is_file():
                    continue
                bad.append(f"{src} → /{p}")
        return bad
