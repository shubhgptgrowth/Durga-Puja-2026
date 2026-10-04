"""Contacts repository export: the people who opted in with a name and phone in My Pujo.

    SUPABASE_ACCESS_TOKEN=… python -m marketing.contacts                 # counts only (Markdown)
    SUPABASE_ACCESS_TOKEN=… python -m marketing.contacts --csv out.csv   # plus the full list

Reads public.contacts_summary() and public.contacts_report() through the Supabase Management API (neither
is callable from the app). Stdout never carries a name or number, so it is safe for a public job summary.
The contacts-export workflow encrypts the CSV before it leaves the runner. Stdlib only.
"""
import argparse
import csv
import json
import os
import re
import sys

from .report import API, _req, config, label

COLUMNS = ["name", "phone", "lang", "first_src", "opted_in", "updated", "days_active", "last_open",
           "pandals", "eateries", "ratings", "avg_stars", "last_visit"]


def query(token, sql):
    url, _ = config()
    ref = re.match(r"https://([a-z0-9]+)\.supabase\.co", url).group(1)
    return _req(f"{API}/projects/{ref}/database/query", {"Authorization": f"Bearer {token}"}, {"query": sql})


def summary_md(s):
    out = ["# Contacts repository", "",
           f"**{s['contacts']}** people have shared a name and number (with consent) · **{s['new_today']}** new today · "
           f"{s['withdrawn']} withdrawals so far", ""]
    if s["by_source"]:
        out += ["| First brought by | People |", "|---|---:|"]
        out += [f"| {label(k)} | {v} |" for k, v in sorted(s["by_source"].items(), key=lambda x: -x[1])]
        out.append("")
    if s["by_lang"]:
        out.append("Language: " + ", ".join(f"{ {'en': 'English', 'bn': 'Bengali', 'hi': 'Hindi'}.get(k, k)} {v}" for k, v in s["by_lang"].items()))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv")
    a = ap.parse_args()
    token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        sys.exit("SUPABASE_ACCESS_TOKEN is not set")
    s = query(token, "select public.contacts_summary() as s")[0]["s"]
    s = json.loads(s) if isinstance(s, str) else s
    print(summary_md(s))
    if a.csv:
        rows = query(token, "select * from public.contacts_report()")
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)
        print(f"\n{len(rows)} rows exported (encrypted file attached to this run).")


if __name__ == "__main__":
    main()
