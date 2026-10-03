"""Usage analytics report: pages, places (pandals, eateries, parking), sounds and actions.

    SUPABASE_ACCESS_TOKEN=… python -m marketing.analytics [--days 1] [--json out.json]

Reads public.analytics_report() through the Supabase Management API. Aggregates only (no device ids),
so the Markdown is fine for the public job summary. The full directory is the `analytics` schema in the
Supabase dashboard (docs/product/ANALYTICS.md). Stdlib only.
"""
import argparse
import json
import os
import sys

from .contacts import query

ACTIONS = {"directions": "Directions taps", "transit": "Transit route taps", "checkin": "Check-in / ate-here taps",
           "rate": "Ratings", "share": "Shares", "filter": "Filter & sort changes", "lang": "Language switches",
           "plan": "Routes built", "trail": "Ready-made trails opened", "moment": "Moments posted"}


def to_md(r):
    live = r.get("live") or {}
    out = [f"# App usage · last {r['days']} day{'s' if r['days'] > 1 else ''}", "",
           f"**{live.get('now_5min', 0)}** on the site now · {live.get('last_hour', 0)} in the last hour · "
           f"{live.get('today', 0)} today · {live.get('all_time', 0)} all time", "",
           f"{r['people']} people did {r['events']} things in this period.", ""]
    if r["pages"]:
        out += ["## Pages", "| Page | Views | People |", "|---|---:|---:|"]
        out += [f"| {p['page']} | {p['views']} | {p['people']} |" for p in r["pages"]]
        out.append("")
    if r["places"]:
        out += ["## Places (top 25 by opens)", "| Place | Kind | Opens | Directions | Check-ins |", "|---|---|---:|---:|---:|"]
        out += [f"| {p.get('name') or p['place_id']} | {p.get('kind') or ''} | {p['opens']} | {p['directions']} | {p['checkins']} |" for p in r["places"]]
        out.append("")
    if r["sounds"]:
        out += ["## Music & sounds", "| Source | What | Taps | People |", "|---|---|---:|---:|"]
        out += [f"| {'Tap pad' if s['source'] == 'sfx' else 'Radio'} | {s['what']} | {s['taps']} | {s['people']} |" for s in r["sounds"][:30]]
        out.append("")
    if r["actions"]:
        out += ["## Actions", "| Action | Times | People |", "|---|---:|---:|"]
        out += [f"| {ACTIONS.get(a['action'], a['action'])} | {a['times']} | {a['people']} |" for a in r["actions"]]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--json")
    a = ap.parse_args()
    token = os.environ.get("SUPABASE_ACCESS_TOKEN") or sys.exit("SUPABASE_ACCESS_TOKEN is not set")
    r = query(token, f"select public.analytics_report({int(a.days)}) as r")[0]["r"]
    r = json.loads(r) if isinstance(r, str) else r
    if a.json:
        json.dump(r, open(a.json, "w"), indent=1)
    print(to_md(r))


if __name__ == "__main__":
    main()
