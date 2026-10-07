"""Card carousels for the daily set: our own words and the guide's own data on every slide, in the route carousel's look.

    {"id": "p3", "type": "photo", "at": "15:30", "render": "cards", "caption": {…},
     "slides": [{"t": "cover", "kicker": "…", "title": ["LINE 1", "LINE 2"], "sub": "…", "pill": "…", "photo": {…}},
                {"t": "item", "kicker": "1/8 · North Kolkata", "name": "Kumartuli Park", "title": "Ganga Tumi Boichho Keno",
                 "body": "…", "foot": "Nearest Metro: Sovabazar · 17 min walk"},
                {"t": "photo", "kicker": "…", "title": "…", "body": "…", "photo": {…}},
                {"t": "end", "title": ["SEND THIS", "TO YOUR PUJO GROUP"], "sub": "…", "pill": "…"}]}
A photo is {"src", "artist", "license", "cx", "cy"}: a Wikimedia Commons file, credited small on the slide itself.
Why cards: since 2026 Instagram keeps unoriginal reposts (photos and carousels too) out of recommendations, and a
caption credit does not make a repost original. Text and data of our own on every slide does.
Writes 1440x1800 JPEGs. Needs Pillow; photos need network.
"""


def check(it):
    errs, sl = [], it.get("slides") or []
    if not 2 <= len(sl) <= 10:
        errs.append(f"{it['id']}: a card carousel needs 2 to 10 slides")
    for k, s in enumerate(sl, 1):
        if s.get("t") not in ("cover", "item", "photo", "end"):
            errs.append(f"{it['id']} slide {k}: unknown type {s.get('t')!r}")
        if not s.get("title"):
            errs.append(f"{it['id']} slide {k}: needs a title")
        p = s.get("photo")
        if p and not (p.get("src") and (p.get("license") == "AI" or (p.get("artist") and p.get("license")))):
            errs.append(f"{it['id']} slide {k}: a photo needs src, artist and license for the credit")
        if s.get("t") == "photo" and not p:
            errs.append(f"{it['id']} slide {k}: a photo slide needs a photo")
    if not (it.get("caption") or {}).get("en"):
        errs.append(f"{it['id']}: a card carousel needs a caption")
    return errs


def build(it, fid, src_dir, out, download):
    from .cards_draw import build as draw
    return draw(it, fid, src_dir, out, download)
