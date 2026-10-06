"""Knowledge articles (content/knowledge/**/*.md) → pages with Article / HowTo / FAQPage / DefinedTermSet data.

Each article also gets a plain Markdown copy next to it (index.md), linked from llms.txt, for AI crawlers."""
import re
import tomllib
from urllib.parse import quote
from pathlib import Path

from .common import NAME, esc, nice_date
from .markdown import render

ISO = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?$")


def minutes(iso):
    m = ISO.match(iso or "")
    return (int(m.group(1) or 0) * 60 + int(m.group(2) or 0)) if m else 0


def human(mins):
    return f"{mins // 60} h {mins % 60} min".replace(" 0 min", "") if mins >= 60 else f"{mins} min"


def share_bar(title, url):
    return (f'<div class="share" aria-label="Share"><a class="sb wa" href="https://wa.me/?text={quote(title + " " + url)}" rel="noopener">WhatsApp</a>'
            '<button class="sb" type="button" data-share="native">Share</button><button class="sb" type="button" data-share="copy">Copy link</button>'
            '<button class="sb" type="button" onclick="print()">Print</button></div>')

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

    def section_list(self, section, up, exclude=None):
        items = sorted((a for a in self.articles if a.section == section and a is not exclude and a.path != "durga-puja/"),
                       key=lambda a: (a.order, a.path))
        return "<ul class='cards'>" + "".join(f"<li><a href='{up}{a.path}'><b>{esc(a.label)}</b><span>{esc(a.desc)}</span></a></li>" for a in items) + "</ul>" if items else ""

    def hub_listing(self, a, up):
        if a.path == "durga-puja/":   # the main hub: everything, by section
            return "".join(f"<h2 id='{s.lower().replace(' ', '-')}'>{esc(s)}</h2>{self.section_list(s, up)}" for s in SECTIONS if self.section_list(s, up))
        return f"<h2 id='in-this-section'>In this section</h2>{self.section_list(a.section, up, exclude=a)}"

    def article_page(self, a):
        up = "../" * a.path.count("/")
        r = render(a.body, up)
        self.article_links[a.path] = list(r.links) + [p for p in a.meta.get("related", [])]
        toc = ("<nav class='toc' aria-label='On this page'><b>On this page</b><ol>" + "".join(f"<li><a href='#{i}'>{esc(t)}</a></li>" for i, t in r.toc)
               + ("<li><a href='#faq'>Frequently asked questions</a></li>" if a.meta.get("faq") else "") + "</ol></nav>") if len(r.toc) >= 3 else ""
        howto = ""
        steps = a.meta.get("steps", [])
        recipe = a.type == "Recipe"
        if recipe:
            g = a.meta.get
            prep, cook = minutes(g("prep_time")), minutes(g("cook_time"))
            facts = [("Serves", g("recipe_yield")), ("Prep", human(prep) if prep else None), ("Cook", human(cook) if cook else None),
                     ("Total", human(prep + cook) if prep + cook else None), ("Diet", g("diet") or None)]
            howto = ("<dl class='recipe-facts'>" + "".join(f"<div><dt>{k}</dt><dd>{esc(v)}</dd></div>" for k, v in facts if v) + "</dl>"
                     + "<h2 id='ingredients'>Ingredients</h2><ul class='checklist'>" + "".join(
                         f'<li><label><input type="checkbox" data-k="i{n}"> {esc(x)}</label></li>' for n, x in enumerate(g("ingredients", [])))
                     + "</ul><h2 id='method'>Method</h2><ol class='steps'>" + "".join(f"<li><b>{esc(st['name'])}</b><p>{esc(st['text'])}</p></li>" for st in steps) + "</ol>")
        elif steps:
            sup = a.meta.get("supplies", [])
            howto = (("<h2 id='what-you-need'>What you need</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in sup) + "</ul>" if sup else "")
                     + "<h2 id='steps'>Step by step</h2><ol class='steps'>" + "".join(f"<li><b>{esc(s['name'])}</b><p>{esc(s['text'])}</p></li>" for s in steps) + "</ol>")
        terms = a.meta.get("terms", [])
        glossary = ("<dl class='glossary'>" + "".join(f"<dt id='{re.sub(r'[^a-z0-9]+', '-', t['term'].lower()).strip('-')}'>{esc(t['term'])}"
                                                       f"{(' <span lang=bn>' + esc(t['alt']) + '</span>') if t.get('alt') else ''}</dt><dd>{esc(t['definition'])}</dd>"
                                                       for t in sorted(terms, key=lambda t: t['term'].lower())) + "</dl>") if terms else ""
        places = [p for p in a.meta.get("places", []) if p in self.pandal]
        places_html = ("<h2 id='see-it-in-kolkata'>See it in Kolkata</h2><ul class='cards'>" + "".join(
            f"<li><a href='{up}guide/pandals/{p}/'><b>{esc(self.pandal[p]['name'])}</b><span>{esc(self.pandal[p]['highlight'])}</span></a></li>" for p in places) + "</ul>") if places else ""
        faq = a.meta.get("faq", [])
        faq_html, faq_ld = self.faq([(f["q"], esc(f["a"])) for f in faq]) if faq else ("", None)
        if faq_html:
            faq_html = faq_html.replace("<section class=\"faq\"><h2>", "<section class=\"faq\"><h2 id=\"faq\">", 1)
        related = [self.by_path[p] for p in a.meta.get("related", []) if p in self.by_path]
        related_html = ("<h2 id='related'>Read next</h2><ul class='cards'>" + "".join(f"<li><a href='{up}{x.path}'><b>{esc(x.label)}</b><span>{esc(x.desc)}</span></a></li>" for x in related) + "</ul>") if related else ""
        sources = a.meta.get("sources", [])
        sources_html = ("<h2 id='sources'>Sources and further reading</h2><ul class='sources'>" + "".join(f"<li><a href='{esc(s['url'])}' rel='noopener'>{esc(s['name'])}</a></li>" for s in sources) + "</ul>") if sources else ""
        hub = self.hub_listing(a, up) if a.is_hub else ""
        words = len(r.text.split()) + len(a.summary.split())
        byline = f"<p class='byline'>{NAME} team · {max(1, round(words / 220))} min read · Updated <time datetime='{a.modified}'>{nice_date(a.modified, True)}</time></p>"
        about = (f"<aside class='about-box'><b>About this guide</b><p>{NAME} is an independent, free guide to Durga Puja. "
                 f"Articles are checked against the sources listed above, say where traditions differ, and are corrected quickly: "
                 f"<a href='{up}contact/'>tell us</a> if you spot one. <a href='{up}about/'>More about us</a>.</p></aside>")
        body = f"""<article>
<h1>{esc(a.h1)}</h1>
{byline}
<p class="lead">{esc(a.summary)}</p>
{share_bar(a.h1, self.url(a.path))}
{toc}
{howto}
<div class="prose">{r.html}</div>
{glossary}
{hub}
{places_html}
{faq_html}
{related_html}
{sources_html}
{about}
</article>"""
        url = self.url(a.path)
        org = {"@type": "Organization", "name": NAME, "url": self.base, "logo": {"@type": "ImageObject", "url": self.url("icons/icon-512.png")}}
        main = {"@context": "https://schema.org", "@type": "Recipe" if recipe else "HowTo" if steps else "Article", "@id": url + "#main", "headline": a.h1[:110], "name": a.h1,
                "description": a.desc, "url": url, "mainEntityOfPage": url, "inLanguage": "en", "datePublished": a.published, "dateModified": a.modified,
                "author": org, "publisher": org, "about": DURGA_PUJA, "image": self.url("icons/og.png"), "isAccessibleForFree": True,
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
                  modified=a.modified, head_extra='<link rel="alternate" type="text/markdown" href="index.md" title="Markdown">')
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
