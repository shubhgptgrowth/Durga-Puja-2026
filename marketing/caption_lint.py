"""Caption and hook checks for the daily review page, from the ig-caption and ig-reel skills
(.claude/skills/, github.com/Jakeschincariol/instagram-agent-skill, MIT).

    python -m marketing.caption_lint 2026-10-08        # print the checks for a day's plan

They only advise: nothing is blocked on them. The skills' checks read English, so Bengali digits are mapped to ASCII
before the "hook is concrete" check, and the hook score is run on the English on-screen hook only.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / ".claude" / "skills"
SEARCH = ["durga puja", "kolkata"]  # the phrases every caption should carry; a plan item adds its own with "search"
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
BENGALI = re.compile(r"[ঀ-৿]")
KEYWORD_LINE = re.compile(r"^\([^()\n]{8,}\)\s*$", re.M)
CREDIT = re.compile(r"(?i)📷|🎥 credits|🎵|\bCC BY|wikimedia commons")
COMMENT_ASK = re.compile(r"(?i)\btell us\b|\bin the comments\b|কমেন্টে|\?\s*👇|\bsend (this|it) to\b|\bshare (this|it) with\b"
                         r"|\btag (a|the|your|someone)\b")  # asks (comment, send, tag) the skill's English patterns miss


def _load(name, rel):
    path = SKILLS / rel
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_caption = _load("ig_caption", "ig-caption/caption.py")
_hooks = _load("ig_hookscore", "ig-reel/hookscore.py")


def caption_notes(text, search=None):
    """WARN/FAIL lines for one caption, plus the visible window as the feed shows it."""
    if not (_caption and text):
        return []
    a = _caption.analyse(text.translate(BN_DIGITS), keywords=SEARCH + list(search or []))
    notes = [f"{c['status']} {c['check'].lower()}: {c['detail']}" for c in a["checks"] if c["status"] != "PASS"
             and not (c["check"] == "ONE ASK" and not a["asks"] and COMMENT_ASK.search(text))]
    if not any(k.lower() in a["visible"].lower() for k in SEARCH + list(search or [])):
        notes.append("NOTE search: no search phrase in the first 125 characters (the part the feed shows)")
    notes += house_notes(text)
    return notes


def house_notes(text):
    """The house layout (marketing/captions.py): English first, keywords in brackets, three tags, no credits."""
    out = []
    first = text.strip().split("\n", 1)[0]
    if BENGALI.search(first):
        out.append("WARN layout: the first line is Bengali; open in English, where search reads it")
    if not KEYWORD_LINE.search(text):
        out.append("NOTE layout: no keyword line in brackets, e.g. (durga puja 2026, kolkata pandal hopping)")
    if len(re.findall(r"(?<!\w)#\w", text)) > 3:
        out.append("WARN layout: more than 3 hashtags; keywords in brackets carry search now")
    if CREDIT.search(text):
        out.append("WARN layout: a credit line in the caption; credits go on the photo or the end card")
    return out


def hook_note(hook):
    if not (_hooks and hook):
        return None
    _, overall, verdict, flags = _hooks.run(hook)
    return f"hook {overall:.0f} {verdict}" + (f" ({'; '.join(flags)})" if flags else "")


def plan_caption(it):
    from .captions import compose
    return compose(it.get("caption"))


def main(argv=None):
    date = (argv or sys.argv[1:])[0]
    plan = json.load(open(ROOT / f"marketing/daily/{date}.json", encoding="utf-8"))
    for it in sorted(plan["items"], key=lambda x: x["at"]):
        text = plan_caption(it)
        if not text:
            continue
        print(f"{it['at']} {it['type']} {it['id']}" + (f" · {hook_note(it['hook'])}" if it.get("hook") else ""))
        for n in caption_notes(text, it.get("search")):
            print("   ", n)


if __name__ == "__main__":
    sys.exit(main())
