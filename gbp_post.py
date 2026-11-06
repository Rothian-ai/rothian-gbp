#!/usr/bin/env python3
"""Write-review-publish for Google Business Profile posts.

Each post is a markdown file in posts/, written by the weekly routine and
reviewed in a pull request. Merging the pull request is the approval: the
publisher only ever sees posts that are on main.

    python3 gbp_post.py check posts/2026-11-10-faster-code.md   # validate a draft
    python3 gbp_post.py list                                    # posts already on the profile
    python3 gbp_post.py publish [--dry-run] [--limit 1]         # post approved, due posts
    python3 gbp_post.py notify-pr <PR URL> posts/<file>.md      # Teams: a draft awaits review

A post file:

    ---
    publish_on: '2026-11-10'      # not posted before this date
    topic: case-study             # service | case-study | insight | news
    cta_url: https://www.rothian.com/case-studies/...
    cta: LEARN_MORE               # optional: LEARN_MORE (default), BOOK, SIGN_UP
    image: https://...jpg         # optional: a public JPG or PNG
    ---
    The text of the post, as it will appear on the profile.

A post is public the moment it is made, so `publish` posts a file only when:
  1. it is on the checked-out branch (the routine checks out main, so it was
     merged), passes `check`, and its publish_on is today or earlier;
  2. the profile does not already carry a post with the same text.

Check 2 makes the profile its own record of what has been posted, so nothing
has to be committed after publishing. Edit a post in its file, not on Google:
a post edited on Google no longer matches its file, and would be posted again.

Failure protocol: any failed step posts {"event":"run_failed"} to
POWERAUTOMATE_WEBHOOK_URL and exits non-zero.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

import requests

TOKEN_URL = "https://oauth2.googleapis.com/token"
POSTS_API = "https://mybusiness.googleapis.com/v4/accounts/{account}/locations/{location}/localPosts"
WEBHOOK = os.environ.get("POWERAUTOMATE_WEBHOOK_URL", "").strip()
SITE_NAME = os.environ.get("GBP_SITE_NAME", "Rothian").strip() or "Rothian"
# Every post's button has to point at the business's own site.
LINK_PREFIX = os.environ.get("GBP_LINK_PREFIX", "https://www.rothian.com/").strip()
POSTS_DIR = Path(__file__).resolve().parent / "posts"

TOPICS = {"service", "case-study", "insight", "news"}
CTAS = {"LEARN_MORE", "BOOK", "SIGN_UP"}
# Business Profile posts carry at most 1,500 characters of text.
MAX_CHARS = 1500
MIN_CHARS = 300

# Google may remove a post that carries contact details in its text ("To avoid
# fraud or abuse, we may remove posts with unverified contact information"), and
# links in the text are not clickable: the button carries the link.
BANNED = [
    (re.compile(r"\+?\d[\d ().-]{7,}\d"), "a phone number"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "an email address"),
    (re.compile(r"(?<![\w.])@\w{2,}"), "a social media handle"),
    (re.compile(r"https?://|www\.", re.I), "a link (put it in cta_url instead)"),
    (re.compile(r"#\w"), "a hashtag"),
]
# House style, warned rather than refused, so a reviewer can choose to keep one.
STYLE = [
    (re.compile("—"), "an em dash"),
    (re.compile("!"), "an exclamation mark"),
]


# ── messaging ──────────────────────────────────────────────────────────

def teams_card(heading: str, facts: list[tuple[str, str]], body: str = "",
               link: tuple[str, str] | None = None) -> dict:
    """An Adaptive Card wrapped the way the Teams "Post to a channel when a
    webhook request is received" workflow expects."""
    items: list[dict] = [{"type": "TextBlock", "text": heading, "weight": "Bolder",
                          "size": "Medium", "wrap": True}]
    if body:
        items.append({"type": "TextBlock", "text": body, "wrap": True})
    items.append({"type": "FactSet",
                  "facts": [{"title": k, "value": v} for k, v in facts if v]})
    card = {"type": "AdaptiveCard", "version": "1.4",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "body": items}
    if link:
        card["actions"] = [{"type": "Action.OpenUrl", "title": link[0], "url": link[1]}]
    return {"type": "message", "attachments": [
        {"contentType": "application/vnd.microsoft.card.adaptive", "content": card}]}


def send(message: dict) -> bool:
    if not WEBHOOK:
        print("  warning: POWERAUTOMATE_WEBHOOK_URL is not set; Teams message not sent",
              file=sys.stderr)
        return False
    try:
        requests.post(WEBHOOK, json=message, timeout=20).raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  warning: Teams message failed: {exc}", file=sys.stderr)
        return False


def fail(reason: str) -> "None":
    print(f"ERROR: {reason}", file=sys.stderr)
    message = {"event": "run_failed", "client": SITE_NAME, "reason": reason}
    message.update(teams_card(f"Business Profile routine FAILED: {SITE_NAME}",
                              [("Site", SITE_NAME), ("Status", "run failed")], body=reason))
    if send(message):
        print("posted run_failed to the webhook", file=sys.stderr)
    sys.exit(1)


# ── post files ─────────────────────────────────────────────────────────

def read_post(path: Path) -> dict:
    md = path.read_text(encoding="utf-8")
    if not md.startswith("---"):
        return {"path": path, "error": "no frontmatter block"}
    _, head, body = md.split("---", 2)
    post = {"path": path, "text": body.strip()}
    for line in head.splitlines():
        m = re.match(r"^([A-Za-z_]+):\s*(.*?)\s*(?:#.*)?$", line)
        if m:
            post[m.group(1)] = m.group(2).strip().strip("'\"")
    return post


def problems(post: dict, online: bool = True) -> tuple[list[str], list[str]]:
    """(errors, warnings). Errors stop a post; warnings are for the reviewer."""
    if "error" in post:
        return [post["error"]], []
    errors, warnings = [], []
    text = post.get("text", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", post.get("publish_on", "")):
        errors.append("publish_on must be a YYYY-MM-DD date")
    if post.get("topic") not in TOPICS:
        errors.append(f"topic must be one of {sorted(TOPICS)}")
    if post.get("cta", "LEARN_MORE") not in CTAS:
        errors.append(f"cta must be one of {sorted(CTAS)}")
    if not (MIN_CHARS <= len(text) <= MAX_CHARS):
        errors.append(f"the text is {len(text)} characters; it must be {MIN_CHARS} to {MAX_CHARS}")
    for pattern, what in BANNED:
        hit = pattern.search(text)
        if hit:
            errors.append(f"the text contains {what}: {hit.group(0)!r}")
    for pattern, what in STYLE:
        if pattern.search(text):
            warnings.append(f"the text contains {what}")
    url = post.get("cta_url", "")
    if not url.startswith(LINK_PREFIX):
        errors.append(f"cta_url must start with {LINK_PREFIX}")
    elif online:
        try:
            r = requests.get(url, timeout=30, allow_redirects=True)
            if r.status_code != 200:
                errors.append(f"cta_url answers {r.status_code}: {url}")
        except requests.RequestException as exc:
            errors.append(f"cta_url could not be reached: {exc}")
    image = post.get("image", "")
    if image and online and not is_photo(image):
        errors.append(f"image is not a reachable JPG or PNG: {image}")
    return errors, warnings


def is_photo(url: str) -> bool:
    """Business Profile photos are documented as JPG or PNG. Some sites answer
    200 with an HTML page for a missing image, so the content type is checked."""
    try:
        r = requests.head(url, timeout=20, allow_redirects=True)
    except requests.RequestException:
        return False
    return r.status_code == 200 and r.headers.get("Content-Type", "").startswith(
        ("image/jpeg", "image/png"))


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


# ── Business Profile API ───────────────────────────────────────────────

def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"{name} is not set (see ROUTINES.md)")
    return value


def api() -> tuple[str, dict]:
    r = requests.post(TOKEN_URL, data={
        "client_id": env("GBP_CLIENT_ID"), "client_secret": env("GBP_CLIENT_SECRET"),
        "refresh_token": env("GBP_REFRESH_TOKEN"), "grant_type": "refresh_token",
    }, timeout=30)
    if r.status_code != 200:
        # invalid_grant almost always means the token was revoked or expired,
        # which happens after 7 days if the consent screen is still in Testing.
        fail(f"Google sign-in failed ({r.status_code}): {r.text[:300]}. If this says "
             "invalid_grant, run gbp_auth.py again and check the OAuth consent screen is "
             "'In production'.")
    url = POSTS_API.format(account=env("GBP_ACCOUNT_ID"), location=env("GBP_LOCATION_ID"))
    return url, {"Authorization": f"Bearer {r.json()['access_token']}"}


def existing_posts(url: str, headers: dict) -> list[dict]:
    posts, page = [], ""
    while True:
        r = requests.get(url, headers=headers, timeout=30,
                         params={"pageSize": 100, **({"pageToken": page} if page else {})})
        if r.status_code != 200:
            fail(f"Listing the profile's posts failed ({r.status_code}): {r.text[:300]}")
        body = r.json()
        posts += body.get("localPosts", [])
        page = body.get("nextPageToken", "")
        if not page:
            return posts


def payload(post: dict) -> dict:
    body = {"languageCode": "en-GB", "summary": post["text"], "topicType": "STANDARD",
            "callToAction": {"actionType": post.get("cta", "LEARN_MORE"),
                             "url": post["cta_url"]}}
    if post.get("image"):
        body["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": post["image"]}]
    return body


# ── commands ───────────────────────────────────────────────────────────

def cmd_check(args) -> None:
    worst = 0
    for name in args.files:
        post = read_post(Path(name))
        errors, warnings = problems(post)
        status = "FAIL" if errors else "ok"
        print(f"{status}  {name}  ({len(post.get('text', ''))} characters)")
        for e in errors:
            print(f"  error:   {e}")
        for w in warnings:
            print(f"  warning: {w}")
        worst = max(worst, 1 if errors else 0)
    sys.exit(worst)


def cmd_list(args) -> None:
    url, headers = api()
    posts = existing_posts(url, headers)
    print(f"{len(posts)} post(s) on the profile, newest first")
    for p in sorted(posts, key=lambda p: p.get("createTime", ""), reverse=True):
        link = (p.get("callToAction") or {}).get("url", "")
        print(f"- {p.get('createTime', '')[:10]}  {p.get('state', '')}  {link}")
        print(f"  {normalise(p.get('summary', ''))[:200]}")


def cmd_publish(args) -> None:
    today = dt.date.today().isoformat()
    files = sorted(POSTS_DIR.glob("*.md"))
    posts = [read_post(path) for path in files]
    due = sorted((p for p in posts if p.get("publish_on", "9999") <= today),
                 key=lambda p: (p["publish_on"], p["path"].name))
    print(f"{len(files)} post file(s), {len(due)} due on or before {today}")

    if args.dry_run and not os.environ.get("GBP_REFRESH_TOKEN", "").strip():
        print("  (no Business Profile credentials: skipping the check against existing posts)")
        url, headers, done = "", {}, set()
    else:
        url, headers = api()
        done = {normalise(p.get("summary", "")) for p in existing_posts(url, headers)}

    made = 0
    for post in due:
        if made >= args.limit:
            break
        if normalise(post.get("text", "")) in done:
            continue
        name = post["path"].name
        # Checked only now, so an old post whose link has since died does not
        # block new ones. An approved post that fails is a problem a person has
        # to fix: it is reported, never skipped silently.
        errors, _ = problems(post)
        if errors:
            fail(f"{name} is approved but does not pass check: {'; '.join(errors)}")
        if args.dry_run:
            print(f"  would post {name}: {payload(post)}")
            made += 1
            continue
        r = requests.post(url, headers=headers, json=payload(post), timeout=60)
        if r.status_code != 200:
            fail(f"Posting {name} to the Business Profile failed ({r.status_code}): {r.text[:300]}")
        made_post = r.json()
        search_url = made_post.get("searchUrl", "")
        print(f"  posted {name} -> {search_url or made_post.get('name', '')}")
        message = {"event": "gbp_posted", "client": SITE_NAME, "file": name,
                   "post_url": search_url, "cta_url": post["cta_url"]}
        message.update(teams_card(
            f"Posted to the {SITE_NAME} Business Profile",
            [("File", name), ("Topic", post["topic"]), ("Button", post["cta_url"])],
            body=post["text"],
            link=("See the post on Google", search_url) if search_url
            else ("Open the linked page", post["cta_url"])))
        send(message)
        made += 1

    if made == 0:
        print("nothing new to post")


def cmd_notify_pr(args) -> None:
    post = read_post(Path(args.file))
    errors, warnings = problems(post, online=False)
    message = {"event": "gbp_post_drafted", "client": SITE_NAME, "pr_url": args.pr_url,
               "file": Path(args.file).name}
    message.update(teams_card(
        f"New {SITE_NAME} Business Profile post for review",
        [("Topic", post.get("topic", "")), ("Goes live", f"on merge, not before {post.get('publish_on', '')}"),
         ("Button", post.get("cta_url", "")), ("Length", f"{len(post.get('text', ''))} characters"),
         ("Notes", "; ".join(errors + warnings))],
        body=post.get("text", ""),
        link=("Review and approve the pull request", args.pr_url)))
    if send(message):
        print("  Teams notification sent")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check", help="validate post files")
    c.add_argument("files", nargs="+")
    c.set_defaults(func=cmd_check)
    l = sub.add_parser("list", help="show the posts already on the profile")
    l.set_defaults(func=cmd_list)
    p = sub.add_parser("publish", help="post approved posts that are due")
    p.add_argument("--dry-run", action="store_true", help="show what would post; posts nothing")
    p.add_argument("--limit", type=int, default=1, help="most posts to make in one run")
    p.set_defaults(func=cmd_publish)
    n = sub.add_parser("notify-pr", help="tell Teams a draft post awaits review")
    n.add_argument("pr_url")
    n.add_argument("file")
    n.set_defaults(func=cmd_notify_pr)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
