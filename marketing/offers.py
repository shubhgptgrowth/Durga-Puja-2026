"""Restaurant pujo offers: list what's waiting for review, approve or reject one.

    SUPABASE_ACCESS_TOKEN=… python -m marketing.offers                       # list (Markdown)
    SUPABASE_ACCESS_TOKEN=… python -m marketing.offers approve <offer-id>    # or reject / pending

Owners post offers from the eatery page; they stay hidden until the team calls the owner back and approves.
The number to call is in the Supabase dashboard (Table editor → schema "analytics" → offers_pending), never
here: this output goes to a public job summary. Stdlib only.
"""
import json
import os
import re
import sys

from .contacts import query

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def esc(v):
    return str(v or "").replace("|", "\\|").replace("\n", " ")


def table_md(rows):
    pending = [r for r in rows if r["status"] == "pending"]
    live = [r for r in rows if r["status"] == "approved"]
    out = ["# Pujo offers", "", f"**{len(pending)}** waiting for a call back · **{len(live)}** live", ""]
    for title, part in (("Waiting for review", pending), ("Live", live)):
        if not part:
            continue
        out += [f"## {title}", "", "| Offer id | Eatery | Offer | Valid | Sent |", "|---|---|---|---|---|"]
        out += [f"| `{r['id']}` | {esc(r['place'])} | **{esc(r['title'])}**{' · ' + esc(r['details']) if r.get('details') else ''} | "
                f"{r['valid_from']} → {r['valid_to']} | {str(r['created_at'])[:16].replace('T', ' ')} |" for r in part]
        out.append("")
    if pending:
        out.append("Call the owner (number in the dashboard: analytics.offers_pending), then run this workflow with "
                   "action `approve` and the offer id.")
    return "\n".join(out)


def main():
    token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        sys.exit("SUPABASE_ACCESS_TOKEN is not set")
    args = sys.argv[1:]
    if args and args[0] != "list":
        action, oid = args[0], (args[1] if len(args) > 1 else "").strip().lower()
        status = {"approve": "approved", "reject": "rejected", "pending": "pending"}.get(action)
        if not status or not UUID.match(oid):
            sys.exit("usage: offers approve|reject|pending <offer-id>")
        r = query(token, f"select public.review_offer('{oid}'::uuid, '{status}') as r")[0]["r"]
        r = json.loads(r) if isinstance(r, str) else r
        print(f"Offer `{oid}` → **{status}** ({r['status']})\n")
        if r["status"] != "ok":
            sys.exit(1)
    rows = query(token, "select public.offers_report() as r")[0]["r"]
    rows = json.loads(rows) if isinstance(rows, str) else rows
    print(table_md(rows))


if __name__ == "__main__":
    main()
