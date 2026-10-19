"""Giveaway draw: valid entries from one post's comments, then a reproducible random draw.

    IG_USER_ID=… IG_ACCESS_TOKEN=… python -m marketing.giveaway --post <permalink or shortcode> --close "2026-10-19 17:00" \
        [--prizes 2,1,1,1] [--alternates 4]

A valid entry (the rules in the giveaway caption): the keyword (PUJO, as for the DM) and at least 3 other accounts
tagged, posted before the close (IST). One entry per person: their first valid comment counts, our own account and
people who only tag themselves don't. The draw is seeded with sha256(post id + close + every entrant, sorted), so
anyone can re-run it from the published seed and get the same winners. Following us can't be read through the API:
the owner checks each winner by hand and moves to the next alternate if they don't follow or don't reply in time.

Prints usernames only (public on the post already); winners' phone numbers go through DMs, never here.
"""
import argparse
import datetime as dt
import hashlib
import random
import re

from .engage import KEYWORDS, creds, words
from .publish_ig import graph

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
TAG = re.compile(r"@([A-Za-z0-9._]+)")


def entries(comments, me, close):
    """[(username, text)] for valid entries, one per person, in comment order."""
    seen, out = set(), []
    for c in sorted(comments, key=lambda c: c["timestamp"]):
        who = (c.get("username") or "").lower()
        if not who or who == me.lower() or who in seen:
            continue
        if dt.datetime.fromisoformat(c["timestamp"].replace("+0000", "+00:00")) > close:
            continue
        text = c.get("text") or ""
        tagged = {t.lower().rstrip(".") for t in TAG.findall(text)} - {who, me.lower()}
        if len(tagged) >= 3 and any(w in KEYWORDS for w in words(text)):
            seen.add(who)
            out.append((who, text))
    return out


def draw(names, media_id, close_iso, n):
    """Seeded draw: the same post, close and entrant list always give the same order."""
    pool = sorted(set(names))
    seed = hashlib.sha256("|".join([media_id, close_iso, *pool]).encode()).hexdigest()
    rng = random.Random(seed)
    return seed, rng.sample(pool, min(n, len(pool)))


def find_media(user, token, post):
    code = post.rstrip("/").split("/")[-1]
    resp = graph("GET", f"{user}/media", token, fields="id,permalink,caption,timestamp", limit="50")
    for m in resp.get("data", []):
        if code in (m["id"], (m.get("permalink") or "").rstrip("/").split("/")[-1]):
            return m
    raise SystemExit(f"post {post} not found among the account's latest 50 posts")


def all_comments(media_id, token):
    out, resp = [], graph("GET", f"{media_id}/comments", token, fields="id,text,username,timestamp", limit="50")
    for _ in range(40):  # up to 2,000 comments
        out += resp.get("data", [])
        nxt = (resp.get("paging") or {}).get("cursors", {}).get("after") if (resp.get("paging") or {}).get("next") else None
        if not nxt:
            break
        resp = graph("GET", f"{media_id}/comments", token, fields="id,text,username,timestamp", limit="50", after=nxt)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--post", required=True, help="the giveaway post's permalink or shortcode")
    ap.add_argument("--close", required=True, help='entries close, IST: "YYYY-MM-DD HH:MM"')
    ap.add_argument("--prizes", default="2,1,1,1", help="passes per winner, first winner first")
    ap.add_argument("--alternates", type=int, default=4)
    a = ap.parse_args(argv)
    user, token = creds()
    me = graph("GET", user, token, fields="username")["username"]
    close = dt.datetime.strptime(a.close, "%Y-%m-%d %H:%M").replace(tzinfo=IST)
    m = find_media(user, token, a.post)
    comments = all_comments(m["id"], token)
    valid = entries(comments, me, close)
    prizes = [int(x) for x in a.prizes.split(",") if x.strip()]
    seed, order = draw([w for w, _ in valid], m["id"], close.isoformat(), len(prizes) + a.alternates)
    print(f"## Giveaway draw · {m.get('permalink')}\n")
    print(f"Entries close {a.close} IST. {len(comments)} comments, **{len(valid)} valid entries** "
          f"(PUJO + 3 people tagged, one per person, before the close).\n")
    print(f"Seed `{seed}` = sha256(post id | close | every valid entrant, sorted). Re-run this to get the same draw.\n")
    print("| # | Winner | Passes | Admits |\n|---:|---|---:|---:|")
    for i, (who, n) in enumerate(zip(order, prizes), 1):
        print(f"| {i} | @{who} | {n} | {4 * n} |")
    alts = order[len(prizes):]
    if alts:
        print("\nAlternates, in order (if a winner doesn't follow us or doesn't reply within the hour): "
              + ", ".join(f"@{w}" for w in alts))
    if len(valid) < len(prizes):
        print(f"\nOnly {len(valid)} valid entries for {len(prizes)} prizes.")


if __name__ == "__main__":
    main()
