"""One caption layout for every post (reels, photo posts, carousels, route reels), built for Instagram search.

    {"en": "Hook with the search phrase in the first line…\n\nBody…\n\nOne ask 👇",
     "bn": "optional: one short Bengali line, only where it adds something",
     "keywords": ["durga puja 2026", "kolkata pandal hopping", …],
     "tags": "#DurgaPuja2026 #KolkataDurgaPuja #PandalHopping"}

English first: the first 125 characters are what the feed shows and what search reads. Keywords go in brackets at the
end, the way search-led creators write them; hashtags are capped at three (Instagram allows five and gives them little
weight). Credits do not go in the caption: the photo and footage credits the CC licences ask for are printed on the
media itself (the photo's corner, the slide's foot, the reel's end card).
"""
MAX_TAGS = 3


def keywords(kw):
    if not kw:
        return ""
    return "(" + (", ".join(kw) if isinstance(kw, (list, tuple)) else str(kw).strip("() ")) + ")"


def compose(c, extra=None):
    """Plan caption dict → the text Instagram gets. A plain string is passed through; extra lines go after the body."""
    if not c:
        return ""
    if isinstance(c, str):
        return c
    tags = " ".join(t for t in (c.get("tags") or "").split() if t.startswith("#"))
    tags = " ".join(tags.split()[:MAX_TAGS])
    parts = [c.get("en", ""), c.get("bn", ""), *(extra or []), keywords(c.get("keywords")), tags]
    return "\n\n".join(x.strip() for x in parts if x and x.strip())
