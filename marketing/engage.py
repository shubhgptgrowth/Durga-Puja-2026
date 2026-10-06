"""Engagement helpers for @pujoparikrama.guide, through the official Graph API only (no bots, no scraping).

    python -m marketing.engage scan --out engage/2026-10-07.json      # read-only: our comments + creators' new posts
    python -m marketing.engage reply marketing/engage/replies/2026-10-07.json [--dry-run]   # post approved replies

scan collects, for the daily engagement brief:
  - comments on our recent posts that we have not answered yet (needs instagram_manage_comments, or
    instagram_business_manage_comments on an Instagram-Login token);
  - the latest posts of the creators in marketing/engage/creators.json, via Business Discovery (Facebook-Login
    token with instagram_basic + pages_read_engagement; the API cannot read other accounts with an Instagram-Login
    token). It only reads public business/creator accounts.
The brief (posts to comment on, drafted comments, drafted replies) is written from this file and reviewed by a person.
Comments on other people's posts and follows are done by hand from the brief: Instagram's API has no endpoint for
them, and automating them through a logged-in bot breaks Instagram's terms and gets new pages action-blocked.

reply posts only replies a person approved: {"replies": [{"comment_id": "…", "text": "…", "approved": true}, …]}.
It never answers the same comment twice (it checks the comment's existing replies first) and spaces replies out.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
from pathlib import Path

from .publish_ig import graph

ROOT = Path(__file__).resolve().parents[1]
CREATORS = ROOT / "marketing" / "engage" / "creators.json"


def creds():
    user, token = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
    if not (user and token):
        raise SystemExit("IG_USER_ID / IG_ACCESS_TOKEN not set")
    return user, token


def safe(fn, *a, **k):
    """A Graph error (missing permission, private account) is reported in the output, not fatal for the scan."""
    try:
        return fn(*a, **k), None
    except SystemExit as e:
        return None, str(e)[:300]


def own_comments(user, token, days=7, me=None):
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    media, err = safe(graph, "GET", f"{user}/media", token, fields="id,caption,permalink,timestamp,comments_count", limit="25")
    if err:
        return [], err
    out = []
    for m in media.get("data", []):
        if dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00")) < since or not m.get("comments_count"):
            continue
        cs, err = safe(graph, "GET", f"{m['id']}/comments", token,
                       fields="id,text,username,timestamp,replies{username,text}", limit="50")
        if err:
            return out, err
        for c in cs.get("data", []):
            if c.get("username") == me:
                continue
            answered = any(r.get("username") == me for r in (c.get("replies") or {}).get("data", []))
            out.append({"comment_id": c["id"], "media": m["permalink"], "post": (m.get("caption") or "")[:120],
                        "from": c.get("username"), "text": c.get("text"), "at": c.get("timestamp"), "answered": answered})
    return out, None


def creator_posts(user, token, handles, per=4, days=4):
    since = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    posts, errors = [], {}
    for h in handles:
        f = (f"business_discovery.username({h}){{username,followers_count,media.limit({per})"
             "{caption,permalink,timestamp,like_count,comments_count,media_type,media_product_type}}")
        r, err = safe(graph, "GET", user, token, fields=f)
        if err:
            errors[h] = err
            continue
        bd = r["business_discovery"]
        for m in bd.get("media", {}).get("data", []):
            t = dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
            if t < since:
                continue
            posts.append({"creator": bd["username"], "followers": bd.get("followers_count"), "permalink": m["permalink"],
                          "caption": (m.get("caption") or "")[:400], "at": m["timestamp"], "likes": m.get("like_count"),
                          "comments": m.get("comments_count"), "type": m.get("media_product_type") or m.get("media_type")})
        time.sleep(1)
    # freshest, most engaged first: commenting early on a post that is taking off is what gets seen
    posts.sort(key=lambda p: ((p["likes"] or 0) + 3 * (p["comments"] or 0)) / (1 + (dt.datetime.now(dt.timezone.utc)
               - dt.datetime.fromisoformat(p["at"].replace("+0000", "+00:00"))).total_seconds() / 3600), reverse=True)
    return posts, errors


def scan(out):
    user, token = creds()
    me = (graph("GET", user, token, fields="username") or {}).get("username")
    handles = [c["handle"].lstrip("@") for c in json.loads(CREATORS.read_text(encoding="utf-8"))["creators"]]
    comments, c_err = own_comments(user, token, me=me)
    posts, p_err = creator_posts(user, token, handles)
    known = {h.lower() for h in handles} | {(me or "").lower()}
    tagged = {}
    for p in posts:  # creators tag the people they collaborate with: the best lead to the next creators to follow
        for h in re.findall(r"@([A-Za-z0-9_.]{3,30})", p["caption"]):
            h = h.rstrip(".")
            if h.lower() not in known:
                tagged[h] = tagged.get(h, 0) + 1
    data = {"scanned_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "account": me,
            "unanswered": [c for c in comments if not c["answered"]], "creator_posts": posts,
            "suggested_creators": sorted(tagged, key=lambda h: -tagged[h])[:15],
            "errors": {"comments": c_err, "creators": p_err}}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(data['unanswered'])} unanswered comments, {len(posts)} creator posts, "
          f"{len(p_err)} creators unreadable{'; comments: ' + c_err if c_err else ''}")


def reply(path, dry):
    user, token = (None, None) if dry else creds()
    me = None if dry else graph("GET", user, token, fields="username").get("username")
    todo = [r for r in json.loads(Path(path).read_text(encoding="utf-8"))["replies"] if r.get("approved")]
    for r in todo:
        if dry:
            print(f"[dry run] reply to {r['comment_id']}: {r['text']}")
            continue
        got = graph("GET", r["comment_id"], token, fields="replies{username}")
        if any(x.get("username") == me for x in (got.get("replies") or {}).get("data", [])):
            print(f"skip {r['comment_id']}: already answered")
            continue
        rid = graph("POST", f"{r['comment_id']}/replies", token, message=r["text"])["id"]
        print(f"replied to {r['comment_id']} → {rid}", flush=True)
        time.sleep(20)  # unhurried, like a person answering
    print(f"{len(todo)} approved replies")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--out", required=True)
    r = sub.add_parser("reply")
    r.add_argument("file")
    r.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    scan(a.out) if a.cmd == "scan" else reply(a.file, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
