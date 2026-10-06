"""One review page for everything marketing/preview.sh rendered: python -m marketing.preview_page preview/

Carousels and posts show every slide in a swipeable row with the caption; reels and stories play inline with their
caption. Each item has Keep / Change / Drop and a note (kept in the browser), and "Copy feedback" puts all of it on
the clipboard to paste into the chat. Nothing on this page posts anything.
"""
import html
import json
import sys
from pathlib import Path

CSS = """
*{box-sizing:border-box}body{margin:0;font:15px/1.45 Inter,system-ui,sans-serif;background:#0f0b0a;color:#f4ece6}
header{position:sticky;top:0;z-index:5;background:rgba(15,11,10,.94);backdrop-filter:blur(8px);padding:12px 16px;border-bottom:1px solid #2a211d;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:18px;margin:0;flex:1}nav a{color:#ffc857;margin-right:12px;text-decoration:none;font-weight:600}
button{font:inherit;border:1px solid #4a3a33;background:#1c1512;color:#f4ece6;border-radius:999px;padding:6px 14px;cursor:pointer}
button.on{background:#ffc857;color:#1a0d0a;border-color:#ffc857}
main{max-width:1100px;margin:auto;padding:16px}h2{margin:32px 0 8px;font-size:22px}
.item{background:#17110f;border:1px solid #2a211d;border-radius:16px;padding:14px;margin:14px 0}
.item h3{margin:0 0 10px;font-size:16px}.row{display:flex;gap:10px;overflow-x:auto;scroll-snap-type:x mandatory;padding-bottom:6px}
.row img{height:420px;border-radius:10px;scroll-snap-align:start;flex:0 0 auto}.row.story img{height:520px}
video{width:100%;max-width:360px;border-radius:12px;background:#000;display:block}
.vid{display:flex;gap:16px;flex-wrap:wrap}.vid pre,.cap{white-space:pre-wrap;font:13px/1.5 Inter,system-ui,sans-serif;color:#cdbfb6;margin:10px 0 0;max-height:220px;overflow:auto;flex:1;min-width:260px}
.fb{display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap}.fb input{flex:1;min-width:200px;background:#0f0b0a;border:1px solid #4a3a33;color:#f4ece6;border-radius:10px;padding:8px}
.hint{color:#ffc857;font-size:13px;margin-top:6px}
@media (max-width:600px){.row img{height:300px}.row.story img{height:380px}}
"""

JS = """
const KEY='pp-preview-fb';let fb={};try{fb=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(fb))}catch(e){}};
document.querySelectorAll('.fb').forEach(el=>{const id=el.dataset.id;const st=fb[id]||{};
  el.querySelectorAll('button').forEach(b=>{if(st.v===b.textContent)b.classList.add('on');b.onclick=()=>{fb[id]={...(fb[id]||{}),v:b.textContent};
    el.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x===b));save()}});
  const i=el.querySelector('input');i.value=st.n||'';i.oninput=()=>{fb[id]={...(fb[id]||{}),n:i.value};save()}});
document.getElementById('copy').onclick=()=>{const lines=Object.entries(fb).filter(([k,v])=>v.v||v.n).map(([k,v])=>`${k}: ${v.v||''}${v.n?' — '+v.n:''}`);
  navigator.clipboard.writeText(lines.join('\\n')||'(no feedback yet)').then(()=>alert(lines.length+' items copied'))};
"""


def fb(item_id):
    return (f'<div class="fb" data-id="{html.escape(item_id)}"><button>Keep</button><button>Change</button><button>Drop</button>'
            f'<input placeholder="What should change?"></div>')


def slides_block(d, rel, item, story=False):
    folder = d / item["id"]
    imgs = sorted(folder.glob("slide-*.jpg"))
    cap = (folder / "caption.txt").read_text(encoding="utf-8") if (folder / "caption.txt").exists() else ""
    row = "".join(f'<img loading="lazy" src="{rel}/{item["id"]}/{p.name}">' for p in imgs)
    hints = "".join(f'<div class="hint">Story sticker: {html.escape(h)}</div>' for h in item.get("hints") or [])
    title = item.get("title") or item["id"]
    return (f'<div class="item"><h3>{html.escape(title)} <small style="opacity:.6">· {len(imgs)} slides</small></h3>'
            f'<div class="row{" story" if story else ""}">{row}</div>{hints}<div class="cap">{html.escape(cap)}</div>{fb(item["id"])}</div>')


def build(root):
    root = Path(root)
    parts, nav = [], []
    reels = sorted((root / "reels").glob("*/manifest.json")) if (root / "reels").exists() else []
    for m in reels:
        man = json.loads(m.read_text(encoding="utf-8"))
        d = man["date"]
        nav.append(f'<a href="#d{d}">Reels {d[8:]}/{d[5:7]}</a>')
        parts.append(f'<h2 id="d{d}">Reels &amp; stories · {d}</h2><p>Voiceover on every reel, hard cuts, subtitles. In posting order (IST).</p>')
        for it in man["items"]:
            src = f"reels/{d}/{it['id']}.mp4"
            parts.append(f'<div class="item"><h3>{html.escape(it["at"])} · {it["type"]} · {html.escape(it["id"])}</h3><div class="vid">'
                         f'<video src="{src}" controls playsinline preload="metadata"></video>'
                         f'<pre>{html.escape(it.get("caption") or "(story: no caption)")}</pre></div>{fb(it["id"])}</div>')
    if (root / "carousels" / "carousels.json").exists():
        spec = json.loads((root / "carousels" / "carousels.json").read_text(encoding="utf-8"))
        nav.append('<a href="#car">Carousels</a>')
        parts.append(f'<h2 id="car">Carousels · {len(spec["carousels"])}</h2><p>Every slide on a real photo of the place it talks about (Wikimedia Commons, credited).</p>')
        parts += [slides_block(root / "carousels", "carousels", c) for c in spec["carousels"]]
    if (root / "posts" / "posts.json").exists():
        spec = json.loads((root / "posts" / "posts.json").read_text(encoding="utf-8"))
        nav.append('<a href="#posts">Posts &amp; stories</a>')
        parts.append('<h2 id="posts">Wave 1 posts &amp; stories</h2><p>Same words, new layouts: real photos, and photoreal AI images only where no real photo of the moment exists.</p>')
        parts += [slides_block(root / "posts", "posts", p, story=p.get("kind") == "story") for p in spec["posts"]]
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Content preview</title><style>{CSS}</style></head><body>
<header><h1>পুজো পরিক্রমা · new look preview</h1><nav>{''.join(nav)}</nav><button id="copy">Copy feedback</button></header>
<main><p>Nothing here is posted. Mark each item Keep / Change / Drop, add a note, then "Copy feedback" and paste it in the chat.</p>
{''.join(parts)}</main><script>{JS}</script></body></html>"""
    (root / "index.html").write_text(page, encoding="utf-8")
    return len(parts)


if __name__ == "__main__":
    print(f"preview page: {build(sys.argv[1] if len(sys.argv) > 1 else 'preview')} blocks")
