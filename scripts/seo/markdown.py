"""The small Markdown subset used by content/knowledge (see its README): ## / ### headings, paragraphs, bold,
italic, links, bullet and numbered lists, pipe tables, > quotes (verses in Bengali or Devanagari become mantra blocks;
"> **Tip:** …" and friends become callout boxes) and ![caption](photo:key) photos. Internal links ("/path/") become relative,
so the pages work under any base URL, and every one is recorded so the build can check it exists."""
import html
import re


def slug(text):
    s = re.sub(r"[^\w\s-]", "", text.lower(), flags=re.UNICODE)
    return re.sub(r"[\s_]+", "-", s).strip("-")[:60] or "section"


def esc_t(s):
    return html.escape(s, quote=False)


class Rendered:
    def __init__(self):
        self.html, self.toc, self.links, self.text = "", [], [], ""


CALLOUT = re.compile(r"^\*\*(Tip|Note|Did you know\?|Good to know|Remember|Etiquette|Safety)[:.]?\*\*:?\s*", re.I)
ICONS = {"tip": "💡", "note": "📝", "did-you-know": "✨", "good-to-know": "✨", "remember": "📌", "etiquette": "🙏", "safety": "⚠️"}
INDIC = re.compile(r"[\u0900-\u09FF]")


def render(md, up="", figure=None):
    """Markdown → Rendered(html, toc [(id, title)], links [internal paths], text). `up` is '../' * depth;
    `figure(key, caption)` returns the HTML for a ![caption](photo:key) line (no figure: the line is dropped)."""
    out = Rendered()

    def inline(s):
        s = html.escape(s, quote=False)

        def link(m):
            label, href = m.group(1), html.unescape(m.group(2)).strip()
            if href.startswith("/"):
                path = href.lstrip("/")
                out.links.append(path.split("#")[0])
                return f'<a href="{up}{html.escape(path, quote=True)}">{label}</a>'
            return f'<a href="{html.escape(href, quote=True)}" rel="noopener">{label}</a>'
        s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", s)
        return s

    lines = md.strip("\n").split("\n")
    parts, i, used = [], 0, set()
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        m = re.match(r"^(#{2,3})\s+(.*)$", line)
        if m:
            level, title = len(m.group(1)), m.group(2).strip()
            hid = slug(re.sub(r"[*_\[\]()]", "", title))
            while hid in used:
                hid += "-2"
            used.add(hid)
            if level == 2:
                out.toc.append((hid, re.sub(r"\*+", "", title)))
            parts.append(f'<h{level} id="{hid}">{inline(title)}</h{level}>')
            i += 1
            continue
        if line.lstrip().startswith("|"):
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
            parts.append('<div class="table"><table><thead><tr>' + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
                         + "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table></div>")
            continue
        m = re.match(r"^!\[([^\]]*)\]\(photo:([\w-]+)\)\s*$", line.strip())
        if m:
            parts.append(figure(m.group(2), m.group(1)) if figure else "")
            i += 1
            continue
        if line.startswith(">"):
            q = []
            while i < len(lines) and lines[i].startswith(">"):
                q.append(lines[i][1:].strip())
                i += 1
            text = "\n".join(q)
            c = CALLOUT.match(text)
            if c:   # > **Tip:** … → a callout box
                kind = re.sub(r"[^a-z]+", "-", c.group(1).lower()).strip("-")
                paras = text[c.end():].split("\n\n")
                parts.append(f'<aside class="callout {kind}"><b class="callout-t"><span aria-hidden="true">{ICONS.get(kind, "💡")}</span> {esc_t(c.group(1))}</b>'
                             + "".join("<p>" + inline(" ".join(x for x in p.split("\n") if x)) + "</p>" for p in paras if p.strip()) + "</aside>")
                continue
            paras = text.split("\n\n")
            cls = ' class="verse"' if INDIC.search(text) else ""
            parts.append(f"<blockquote{cls}>" + "".join("<p>" + "<br>".join(inline(x) for x in p.split("\n") if x) + "</p>" for p in paras if p.strip()) + "</blockquote>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+", line)
        if m:
            ordered = m.group(2)[0].isdigit()
            items = []
            while i < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                item = re.sub(r"^\s*([-*]|\d+\.)\s+", "", lines[i]).strip()
                i += 1
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"^\s*([-*]|\d+\.)\s+", lines[i]):
                    item += " " + lines[i].strip()
                    i += 1
                items.append(item)
            tag = "ol" if ordered else "ul"
            if items and all(re.match(r"^\[[ xX]\]\s", x) for x in items):   # "- [ ] item": a tick-box checklist
                lis = []
                for n, x in enumerate(items):
                    text = x[3:].strip()
                    lis.append(f'<li><label><input type="checkbox" data-k="{n}-{slug(text)[:30]}"> {inline(text)}</label></li>')
                parts.append('<ul class="checklist">' + "".join(lis) + "</ul>")
            else:
                parts.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{2,3}\s|>|\||\s*([-*]|\d+\.)\s)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        parts.append("<p>" + inline(" ".join(para)) + "</p>")
    out.html = "\n".join(parts)
    out.text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", out.html))).strip()
    return out
