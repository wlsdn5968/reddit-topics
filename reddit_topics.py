#!/usr/bin/env python3
"""Read-only Reddit topic checker for a personal, ad-free blog.

What it does (and nothing else):
  * Gets an application-only OAuth token (grant_type=client_credentials,
    "script" app) from https://www.reddit.com/api/v1/access_token.
  * Reads the top listing of a fixed list of public subreddits from
    https://oauth.reddit.com/r/<subreddit>/top?t=<period>&limit=<n>.
  * Keeps only title, score, num_comments and permalink of each post.

What it never does:
  * No posting, commenting, voting or messaging (read-only, no user login).
  * No user profiles, private data or comment bodies.
  * Does not republish Reddit content and does not use it to train any
    machine learning or AI model.
  * Saved files (optional --save) are deleted after 48 hours on the next run.

Credentials come from environment variables only (never stored in this file):
  REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME (used in User-Agent)

Python 3.9+ standard library only.

References: Reddit Data API Wiki, Responsible Builder Policy, Data API Terms,
and the OAuth2 "Application Only OAuth" section of the reddit-archive wiki.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

VERSION = "0.1.0"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"
# The subreddits named in the access request. Others are refused on purpose.
ALLOWED_SUBREDDITS = ("technology", "privacy", "gadgets")
PERIODS = ("hour", "day", "week", "month", "year", "all")
MAX_LIMIT = 100          # listing maximum
PAUSE_SECONDS = 2.0      # wait between requests (far below the free limit)
KEEP_HOURS = 48          # delete saved files older than this


def user_agent(username: str) -> str:
    # Format required by Reddit: <platform>:<app ID>:<version> (by /u/<username>)
    return f"script:naver-blog-topics:v{VERSION} (by /u/{username})"


def http_json(req: urllib.request.Request) -> tuple[dict, dict]:
    with urllib.request.urlopen(req, timeout=30) as resp:
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return json.loads(resp.read().decode("utf-8")), headers


def get_token(client_id: str, client_secret: str, ua: str) -> str:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST", headers={
        "Authorization": f"Basic {basic}", "User-Agent": ua})
    body, _ = http_json(req)
    if body.get("token_type") != "bearer" or "access_token" not in body:
        sys.exit("stop: token request did not return a bearer token")
    return body["access_token"]


def read_top(subreddit: str, period: str, limit: int, token: str, ua: str) -> list[dict]:
    url = f"{API_BASE}/r/{subreddit}/top?" + urllib.parse.urlencode({"t": period, "limit": limit})
    req = urllib.request.Request(url, headers={"Authorization": f"bearer {token}", "User-Agent": ua})
    body, headers = http_json(req)
    remaining = headers.get("x-ratelimit-remaining")
    if remaining is not None and float(remaining) < 5:
        sys.exit(f"stop: rate limit almost used (X-Ratelimit-Remaining={remaining})")
    posts = []
    for child in body.get("data", {}).get("children", []):
        d = child.get("data", {})
        posts.append({
            "subreddit": subreddit,
            "title": d.get("title", ""),
            "score": d.get("score"),
            "num_comments": d.get("num_comments"),
            "permalink": "https://www.reddit.com" + d.get("permalink", ""),
        })
    return posts


def prune(save_dir: Path) -> int:
    cutoff = time.time() - KEEP_HOURS * 3600
    removed = 0
    for f in save_dir.glob("reddit-top-*.json"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            removed += 1
    return removed


def main() -> None:
    p = argparse.ArgumentParser(description="Read-only Reddit top-post checker (titles/scores only)")
    p.add_argument("--subreddits", default=",".join(ALLOWED_SUBREDDITS),
                   help="comma-separated, must be within the allowed list")
    p.add_argument("--period", default="day", choices=PERIODS)
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--save", metavar="DIR", help="also save JSON here (files older than 48h are deleted)")
    p.add_argument("--dry-run", action="store_true", help="print the planned requests without any network call")
    a = p.parse_args()

    subs = [s.strip().lower().removeprefix("r/") for s in a.subreddits.split(",") if s.strip()]
    bad = [s for s in subs if s not in ALLOWED_SUBREDDITS]
    if bad:
        sys.exit(f"stop: not in the allowed list {ALLOWED_SUBREDDITS}: {bad}")
    if not 1 <= a.limit <= MAX_LIMIT:
        sys.exit(f"stop: --limit must be 1..{MAX_LIMIT}")

    username = os.environ.get("REDDIT_USERNAME", "").strip()
    ua = user_agent(username or "<REDDIT_USERNAME>")
    if a.dry_run:
        print(f"User-Agent: {ua}")
        print(f"POST {TOKEN_URL}  (grant_type=client_credentials, HTTP Basic client_id:secret)")
        for s in subs:
            print(f"GET  {API_BASE}/r/{s}/top?t={a.period}&limit={a.limit}")
        print(f"requests: {1 + len(subs)}, pause {PAUSE_SECONDS}s between listing requests")
        return

    cid = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    if not (cid and secret and username):
        sys.exit("stop: set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET and REDDIT_USERNAME")

    token = get_token(cid, secret, ua)
    rows = []
    for i, s in enumerate(subs):
        if i:
            time.sleep(PAUSE_SECONDS)
        rows += read_top(s, a.period, a.limit, token, ua)

    rows.sort(key=lambda r: (r["score"] or 0), reverse=True)
    for r in rows:
        print(f"[{r['score']:>6}pt {r['num_comments']:>5}c] r/{r['subreddit']} | {r['title']}\n    {r['permalink']}")

    if a.save:
        d = Path(a.save)
        d.mkdir(parents=True, exist_ok=True)
        removed = prune(d)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out = d / f"reddit-top-{stamp}.json"
        out.write_text(json.dumps({"fetched_at": stamp, "period": a.period, "posts": rows},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"saved {out} (removed {removed} file(s) older than {KEEP_HOURS}h)")


if __name__ == "__main__":
    main()
