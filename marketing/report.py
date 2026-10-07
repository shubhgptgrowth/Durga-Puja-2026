"""Daily reach report for the marketing push: how many devices opened the app, and which links brought them.

    SUPABASE_ACCESS_TOKEN=… python -m marketing.report [--target 100000] [--json out.json]

Reads public.growth_report() through the Supabase Management API (the function is not callable from
the app), plus the public place_stats view for check-ins. Prints Markdown, which the marketing-report
workflow puts in its job summary. Stdlib only.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.supabase.com/v1"

LABELS = {"direct": "Direct / typed / home screen", "ig_bio": "Instagram bio link", "ig_story": "Instagram story link",
          "ig_mycard": "My Pujo card shares", "wa_channel": "WhatsApp Channel", "wa_fwd": "WhatsApp forwards",
          "wa_place": "WhatsApp place shares", "share": "Share button", "plan_share": "Shared routes", "qr_flyer": "QR flyer", "other": "Other",
          "seo_google": "Google search → guide page", "seo_bing": "Bing search → guide page", "seo_other": "Other search → guide page",
          "ai_answer": "AI answer (ChatGPT, Perplexity, Copilot…) → guide page", "guide_direct": "Guide page, no referrer"}


def label(src):
    if src in LABELS:
        return LABELS[src]
    if src.startswith("qr_") and src != "qr_flyer":
        return f"QR poster · {src[3:]}"
    if src.startswith("creator_"):
        return f"Creator · {src[8:]}"
    if src.startswith("committee_"):
        return f"Puja committee · {src[10:]}"
    if src.startswith("press_"):
        return f"Press · {src[6:]}"
    if src.startswith("ref_"):
        return f"Link from another site · {src[4:]}"
    if src.startswith("seo_"):
        return f"Guide page → app · {src[4:]}"
    return LABELS.get(src, src)


def config():
    s = (ROOT / "app" / "config.js").read_text(encoding="utf-8")
    url = re.search(r"url: '([^']*)'", s).group(1)
    key = re.search(r"anonKey: '([^']*)'", s).group(1)
    return url, key


def _req(url, headers, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={**headers, "Content-Type": "application/json", "User-Agent": "pujo-parikrama-report"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch(token):
    url, key = config()
    ref = re.match(r"https://([a-z0-9]+)\.supabase\.co", url).group(1)
    rows = _req(f"{API}/projects/{ref}/database/query", {"Authorization": f"Bearer {token}"}, {"query": "select public.growth_report(30) as r"})
    report = rows[0]["r"]
    if isinstance(report, str):
        report = json.loads(report)
    stats = _req(f"{url}/rest/v1/place_stats?select=place_id,kind,visits,today", {"apikey": key})
    return report, stats


def bar(n, top, width=20):
    return "█" * max(1, round(width * n / top)) if top else ""


def markdown(r, stats, target):
    total, today = r.get("devices_total", 0), r.get("devices_today", 0)
    pct = 100 * total / target if target else 0
    checkins = sum(s["visits"] for s in stats if s["kind"] == "pandal")
    ate = sum(s["visits"] for s in stats if s["kind"] == "food")
    today_ci = sum(s["today"] for s in stats)
    out = [f"## Pujo Parikrama reach · {r.get('generated_at', '')[:16].replace('T', ' ')} UTC", "",
           f"**{total:,} devices** have opened the app ({pct:.1f}% of the {target:,} goal). **{today:,} today.**", "",
           f"Check-ins: {checkins:,} at pandals, {ate:,} 'I ate here', {today_ci:,} today. People who checked in at least once: {r.get('checked_in_people', 0):,}.", "",
           "### Devices per day", "", "| Day | Devices | New | Opens | |", "|---|---:|---:|---:|---|"]
    days = r.get("by_day") or []
    top = max((d["people"] for d in days), default=0)
    out += [f"| {d['day']} | {d['people']:,} | {d['new']:,} | {d['opens']:,} | {bar(d['people'], top)} |" for d in days]
    out += ["", "### What first brought people in", "", "| Source | Devices | |", "|---|---:|---|"]
    src = r.get("by_first_source") or []
    top = max((s["people"] for s in src), default=0)
    out += [f"| {label(s['src'])} (`{s['src']}`) | {s['people']:,} | {bar(s['people'], top)} |" for s in src[:25]]
    t = r.get("today_by_source") or []
    if t:
        out += ["", "### Today's opens by link", "", "| Source | Devices |", "|---|---:|"]
        out += [f"| {label(s['src'])} | {s['people']:,} |" for s in t[:15]]
    hot = sorted((s for s in stats if s["today"]), key=lambda s: -s["today"])[:10]
    if hot:
        out += ["", "### Busiest places today (check-ins)", "", "| Place | Today | All time |", "|---|---:|---:|"]
        g = json.loads((ROOT / "app" / "data" / "guide.json").read_text(encoding="utf-8"))
        names = {p["id"]: p["name"] for p in g["pandals"] + g["food"]}
        out += [f"| {names.get(s['place_id'], s['place_id'])} | {s['today']:,} | {s['visits']:,} |" for s in hot]
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--target", type=int, default=int(os.environ.get("REACH_TARGET") or 100000))
    ap.add_argument("--json", help="also write the raw report here")
    a = ap.parse_args(argv)
    token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        sys.exit("Set SUPABASE_ACCESS_TOKEN (the repository secret used by supabase-setup).")
    r, stats = fetch(token)
    if a.json:
        Path(a.json).write_text(json.dumps({"report": r, "place_stats": stats}, indent=1), encoding="utf-8")
    print(markdown(r, stats, a.target))


if __name__ == "__main__":
    main()
