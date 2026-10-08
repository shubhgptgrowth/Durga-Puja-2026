"""Engagement helpers for @pujoparikrama.guide, through the official Graph API only (no bots, no scraping).

    python -m marketing.engage scan --out engage/2026-10-07.json      # read-only: our comments + creators' new posts
    python -m marketing.engage reply marketing/engage/replies/2026-10-07.json [--dry-run]   # post approved replies
    python -m marketing.engage dm --ledger dm.json [--dry-run]          # comment "PUJO" -> the guide in a private reply
    python -m marketing.engage check                                    # read-only: can the token do all of the above?
    python -m marketing.engage stats --out stats/2026-10-08.json         # read-only: every post's numbers, by format

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


def page_token(token, page):
    """Messages go out through the Facebook Page and need the Page's own token. A saved user token (Graph API
    Explorer, Facebook Login) is swapped for it here; a Page token or an Instagram-Login token is used as it is."""
    if not page or token.startswith("IG"):
        return token
    r, e = safe(graph, "GET", page, token, fields="access_token")
    return (r or {}).get("access_token") or token


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


KEYWORDS = ("pujo", "পুজো", "পূজো", "route", "রুট")
DM_BN = ("নমস্কার! 🙏 এই নিন আপনার পুজোর রুট গাইড: এলাকা ধরে হাঁটার রুট, কোন মেট্রো স্টেশনে নামবেন, "
         "আর কোন ঠাকুর কখন ফাঁকা থাকে, সব এক জায়গায়, একদম ফ্রি।")
DM_EN = ("Here's your Durga Puja 2026 route guide: area-wise walking routes, the Metro stop for each, and live "
         "quiet hours for every pandal. Free, no sign-up:")
GUIDE = "https://pujoparikramaguide.in/?src=ig_dm"


def wants_guide(text):
    t = (text or "").lower()
    return any(k in t for k in KEYWORDS)


def dm(ledger_path, dry, days=7):
    """Comment-to-DM (the owner asked for it, 7 Oct): whoever comments the keyword ("PUJO") on one of our recent posts
    gets one private reply with the guide (Instagram's Private Replies API: one message per comment, within 7 days of
    it) and a short public reply. The ledger of answered comment ids lives on the engage-data branch, so nobody is
    messaged twice; only people who asked by commenting are ever messaged."""
    user, token = creds()
    me = graph("GET", user, token, fields="username").get("username")
    ledger = json.loads(Path(ledger_path).read_text(encoding="utf-8")) if Path(ledger_path).exists() else {"sent": []}
    sent = set(ledger["sent"])
    comments, err = own_comments(user, token, days=days, me=me)
    if err:
        raise SystemExit(f"cannot read comments: {err}")
    todo = [c for c in comments if wants_guide(c["text"]) and c["comment_id"] not in sent]
    page = os.environ.get("IG_PAGE_ID")  # Facebook-Login tokens send through the Page; Instagram-Login through the account
    send = page_token(token, page)
    done = 0
    for c in todo[:40]:  # at most 40 a run, spaced out
        if dry:
            print(f"[dry run] DM @{c['from']} (comment {c['comment_id']}: {c['text'][:40]!r})")
            continue
        msg = json.dumps({"text": f"{DM_BN}\n\n{DM_EN}\n{GUIDE}"}, ensure_ascii=False)
        r, e = safe(graph, "POST", f"{page or user}/messages", send,
                    recipient=json.dumps({"comment_id": c["comment_id"]}), message=msg)
        if e:
            print(f"DM to @{c['from']} failed: {e}", flush=True)
            continue
        safe(graph, "POST", f"{c['comment_id']}/replies", token, message="DM-এ পাঠিয়ে দিলাম 💛 Sent to your DMs!")
        sent.add(c["comment_id"])
        done += 1
        print(f"DM sent to @{c['from']}", flush=True)
        time.sleep(8)
    ledger["sent"] = sorted(sent)
    Path(ledger_path).write_text(json.dumps(ledger, indent=1), encoding="utf-8")
    print(f"{done} DMs sent, {len(todo) - done} pending, {len(sent)} in ledger")


def check():
    """Read-only token check, for after a new token is saved: nothing is posted or sent. A dm --dry-run never calls
    the messaging endpoint, so this reads the inbox instead, which needs the same permission and the "Allow access
    to messages" switch in the Instagram app."""
    user, token = creds()
    page = os.environ.get("IG_PAGE_ID")
    ok = True

    def step(name, fn, *a, **k):
        nonlocal ok
        r, e = safe(fn, *a, **k)
        print(f"{'ok  ' if e is None else 'FAIL'} {name}" + (f": {e}" if e else ""), flush=True)
        ok = ok and e is None
        return r

    if not token.startswith("IG"):  # a token can inspect itself: which permissions it really carries, and until when
        d, e = safe(graph, "GET", "debug_token", token, input_token=token)
        if d:
            d = d.get("data", {})
            exp = d.get("expires_at") or 0
            until = f"expires {dt.datetime.fromtimestamp(exp, dt.timezone.utc):%Y-%m-%d}" if exp else "never expires"
            print(f"     token: {d.get('type')}, app {d.get('application')}, valid {d.get('is_valid')}, {until}")
            print(f"     permissions: {', '.join(sorted(d.get('scopes', []))) or 'none'}")
            for sc in ("instagram_basic", "instagram_manage_comments", "instagram_manage_messages", "pages_show_list",
                       "pages_read_engagement", "pages_manage_metadata"):
                if sc not in d.get("scopes", []):
                    print(f"     missing: {sc}")
        else:
            print(f"     token details unavailable: {e}")
    acct = step("account", graph, "GET", user, token, fields="username")
    if acct:
        print(f"     @{acct.get('username')}")
    step("our posts and their comments", graph, "GET", f"{user}/media", token, fields="id,comments_count", limit="1")
    if page:
        p = step("Facebook Page", graph, "GET", page, token, fields="name,instagram_business_account")
        if p:
            linked = (p.get("instagram_business_account") or {}).get("id")
            print(f"     {p.get('name')} · linked Instagram account {'matches IG_USER_ID' if linked == user else 'does NOT match IG_USER_ID'}")
            ok = ok and linked == user
    step("messages (comment-to-DM)", graph, "GET", f"{page or user}/conversations", page_token(token, page),
         platform="instagram", limit="1")
    handles = [c["handle"].lstrip("@") for c in json.loads(CREATORS.read_text(encoding="utf-8"))["creators"]]
    step(f"creator posts (@{handles[0]}, Business Discovery)", graph, "GET", user, token,
         fields=f"business_discovery.username({handles[0]}){{username}}")
    print("all checks passed" if ok else "some checks failed")
    return 0 if ok else 1


FORMAT = {"cards": "carousel (cards)", "routes": "carousel (route map)", "cards_reel": "reel (from carousel)",
          "route": "reel (route map)"}


def plan_index():
    """Caption start → (date, plan id, format, hook) for everything in marketing/daily, to label each post."""
    from .captions import compose
    idx = {}
    for f in sorted((ROOT / "marketing" / "daily").glob("2*.json")):
        plan = json.loads(f.read_text(encoding="utf-8"))
        for it in plan["items"]:
            cap = compose(it.get("caption")) if it.get("caption") else ""
            if not cap:
                continue
            fmt = FORMAT.get(it.get("render")) or ("carousel (photos)" if it["type"] == "photo" and len(it.get("photos") or []) > 1
                                                    else "photo" if it["type"] == "photo" else "reel (footage)")
            row = {"date": plan["date"], "id": it["id"], "at": it["at"], "format": fmt, "hook": it.get("hook", "")}
            c = it["caption"]
            legacy = "\n\n".join(x for x in (c.get("bn", ""), c.get("en", "")) if x) if isinstance(c, dict) else ""
            for text in (cap, legacy):  # posts before 7 Oct went out Bengali first
                if text:
                    idx[" ".join(text.split())[:60]] = row
    return idx


def stats(out):
    """Read-only: likes and comments for every post (and reach, saves, shares, views when the token carries
    instagram_manage_insights), each labelled with its plan item and format, so formats can be compared."""
    user, token = creds()
    media, err = safe(graph, "GET", f"{user}/media", token, limit="50",
                      fields="id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count")
    if err:
        raise SystemExit(f"cannot read posts: {err}")
    idx = plan_index()
    rows, ins_err = [], None
    for m in media.get("data", []):
        key = " ".join((m.get("caption") or "").split())[:60]
        row = {"media": m["id"], "at": m["timestamp"], "type": m.get("media_product_type") or m.get("media_type"),
               "likes": m.get("like_count"), "comments": m.get("comments_count"), "permalink": m.get("permalink"),
               "first_line": (m.get("caption") or "").split("\n")[0][:90], **idx.get(key, {"format": "unplanned"})}
        if ins_err is None or "permission" not in ins_err:
            metrics = "reach,saved,shares,views" if row["type"] == "REELS" else "reach,saved,shares"
            ins, e = safe(graph, "GET", f"{m['id']}/insights", token, metric=metrics)
            if ins:
                row.update({x["name"]: (x.get("values") or [{}])[0].get("value", x.get("total_value", {}).get("value"))
                            for x in ins.get("data", [])})
            else:
                ins_err = e
        rows.append(row)
    by = {}
    for r in rows:
        b = by.setdefault(r["format"], {"posts": 0, "likes": 0, "comments": 0})
        b["posts"] += 1
        b["likes"] += r["likes"] or 0
        b["comments"] += r["comments"] or 0
    data = {"taken_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "posts": rows,
            "by_format": by, "insights_error": ins_err}
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} posts" + ("" if not ins_err else " (likes and comments only: no insights permission)"))
    for f, b in sorted(by.items(), key=lambda kv: -(kv[1]["likes"] + 3 * kv[1]["comments"]) / kv[1]["posts"]):
        print(f"  {f:24s} {b['posts']:3d} posts · {b['likes'] / b['posts']:.1f} likes · {b['comments'] / b['posts']:.1f} comments per post")
    for r in sorted(rows, key=lambda r: -((r["likes"] or 0) + 3 * (r["comments"] or 0)))[:5]:
        print(f"  top: {r['likes']} likes, {r['comments']} comments · {r['format']} · {r['first_line'][:60]}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("--out", required=True)
    m = sub.add_parser("dm")
    m.add_argument("--ledger", required=True)
    m.add_argument("--dry-run", action="store_true")
    r = sub.add_parser("reply")
    r.add_argument("file")
    r.add_argument("--dry-run", action="store_true")
    sub.add_parser("check")
    st = sub.add_parser("stats")
    st.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "check":
        return check()
    if a.cmd == "stats":
        return stats(a.out)
    if a.cmd == "scan":
        scan(a.out)
    elif a.cmd == "dm":
        dm(a.ledger, a.dry_run)
    else:
        reply(a.file, a.dry_run)


if __name__ == "__main__":
    sys.exit(main())
