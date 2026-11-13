#!/usr/bin/env python3
"""Share each new rothian.com insight on Rothian's Google Business Profile, with
an illustration, after a person approves it.

    python3 gbp_post.py prepare [--limit 1]            # draft a post for the next new insight
    python3 gbp_post.py image posts/<file>.md          # generate its image from image_prompt
    python3 gbp_post.py check posts/<file>.md          # validate a post
    python3 gbp_post.py notify-pr <PR URL> posts/<file>.md
    python3 gbp_post.py publish [--dry-run] [--limit 1]
    python3 gbp_post.py list                           # posts already on the profile

The flow:
  1. `prepare` reads the site's sitemap (GBP_SITEMAP_URL), finds the oldest
     insight dated on or after GBP_POST_SINCE that has no post yet, and writes
     posts/<date>-<slug>.md: the insight's title and description in the
     frontmatter, and a caption to fill in (hook, summary, call to action).
  2. The routine reads the insight, writes the hook and summary, writes an
     image_prompt (the subject only), and runs `image`, which adds Rothian's
     fixed visual style (brand/image-style.txt) and makes
     posts/images/<slug>.jpg with the OpenAI API.
  3. The routine opens a draft pull request. Merging it is the approval.
  4. `publish` posts merged posts. Google takes a post's image only as a public
     URL (sourceUrl), so the image is served from main at GBP_IMAGE_BASE_URL:
     it becomes reachable when the pull request is merged, not before.

A post is public the moment it is made, so `publish` posts a file only when it
is on the checked-out branch (the routine checks out main, so it was merged),
passes `check`, its image is publicly reachable, and the profile does not
already carry a post linking to the same insight. The profile is its own
record of what has been posted: nothing is committed after publishing.

A post file:

    ---
    publish_on: '2026-11-07'
    cta_url: https://www.rothian.com/insights/<slug>
    article_date: '2026-11-03'
    image: <slug>.jpg
    image_prompt: '...'
    insight_title: '...'
    insight_description: '...'
    ---
    A one-line hook.

    A short summary of the insight.

    A call to action pointing at the Learn more button.

Failure protocol: any failed step posts {"event":"run_failed"} to
POWERAUTOMATE_WEBHOOK_URL and exits non-zero.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "posts"
IMAGES_DIR = POSTS_DIR / "images"
# Appended to every image_prompt, so every post has the same brand look.
STYLE_FILE = ROOT / "brand" / "image-style.txt"

TOKEN_URL = "https://oauth2.googleapis.com/token"
POSTS_API = "https://mybusiness.googleapis.com/v4/accounts/{account}/locations/{location}/localPosts"
OPENAI_API = "https://api.openai.com/v1/images/generations"

WEBHOOK = os.environ.get("POWERAUTOMATE_WEBHOOK_URL", "").strip()
SITE_NAME = os.environ.get("GBP_SITE_NAME", "Rothian").strip() or "Rothian"
SITEMAP = os.environ.get("GBP_SITEMAP_URL", "https://www.rothian.com/sitemap.xml").strip()
PATH_PREFIX = os.environ.get("GBP_PATH_PREFIX", "/insights/").strip() or "/insights/"
# Every post's button has to point at the business's own site.
LINK_PREFIX = os.environ.get("GBP_LINK_PREFIX", "https://www.rothian.com/").strip()
# Where Google fetches a merged post's image from. The default is this
# repository's main branch, which has to be public for Google to reach it.
IMAGE_BASE = os.environ.get(
    "GBP_IMAGE_BASE_URL",
    "https://raw.githubusercontent.com/Rothian-ai/rothian-gbp/main/posts/images/").strip()
if not IMAGE_BASE.endswith("/"):
    IMAGE_BASE += "/"
# gpt-image-1 was refused for this organisation's key; 1.5 worked.
IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1.5").strip() or "gpt-image-1.5"
IMAGE_SIZE = os.environ.get("OPENAI_IMAGE_SIZE", "1536x1024").strip() or "1536x1024"

# Business Profile posts carry at most 1,500 characters of text.
MAX_CHARS = 1500
MIN_CHARS = 80
# The hook is the first paragraph: Google shows only the first lines of a post
# before "More", so it has to be short.
MAX_HOOK_CHARS = 150
# The caption's placeholders, written by `prepare` and filled in by the routine.
HOOK_PLACEHOLDER = "[HOOK: one line that makes a buyer stop]"
SUMMARY_PLACEHOLDER = "[SUMMARY: two or three sentences on what the insight says]"
# The button Google shows for actionType LEARN_MORE; the CTA points at it.
BUTTON_LABEL = "Learn more"
CTA_TEXT = os.environ.get(
    "GBP_CTA_TEXT", f"Read the full insight on our website: tap {BUTTON_LABEL}.").strip()
# Google's minimum for a photo it hosts.
MIN_IMAGE_BYTES = 10240

# Google may remove a post that carries contact details in its text ("To avoid
# fraud or abuse, we may remove posts with unverified contact information"), and
# links in the text are not clickable: the button carries the link.
BANNED = [
    (re.compile(r"\+?\d[\d ().-]{7,}\d"), "a phone number"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "an email address"),
    (re.compile(r"(?<![\w.])@\w{2,}"), "a social media handle"),
    (re.compile(r"https?://|www\.", re.I), "a link (the button carries the link)"),
    (re.compile(r"#\w"), "a hashtag"),
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


def env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        fail(f"{name} is not set (see ROUTINES.md)")
    return value


# ── the site ───────────────────────────────────────────────────────────

def meta(page: str, key: str) -> str:
    """A <meta property|name="key" content="..."> value, in either attribute order."""
    for pattern in (rf'<meta (?:property|name)="{re.escape(key)}" content="([^"]*)"',
                    rf'<meta content="([^"]*)" (?:property|name)="{re.escape(key)}"'):
        m = re.search(pattern, page)
        if m:
            return html.unescape(m.group(1)).strip()
    return ""


def site_insights(since: str) -> list[dict]:
    """Insights listed in the sitemap under PATH_PREFIX, read from the live site,
    oldest first. A page that does not answer 200 or carries no publish date is
    skipped: without a date it cannot be held to GBP_POST_SINCE."""
    r = requests.get(SITEMAP, timeout=30)
    if r.status_code != 200:
        fail(f"Reading the sitemap {SITEMAP} failed ({r.status_code})")
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as exc:
        fail(f"The sitemap {SITEMAP} is not valid XML: {exc}")
    found = []
    for el in root.iter():
        if not (el.tag.endswith("loc") and el.text):
            continue
        url = el.text.strip().rstrip("/")
        path = urlparse(url).path
        if not path.startswith(PATH_PREFIX) or path.rstrip("/") == PATH_PREFIX.rstrip("/"):
            continue
        try:
            page = requests.get(url, timeout=30)
        except requests.RequestException:
            continue
        if page.status_code != 200:
            continue
        date = (meta(page.text, "article:published_time")
                or (re.search(r'"datePublished":"([^"]+)"', page.text) or [None, ""])[1])[:10]
        if not date or date < since:
            continue
        title = meta(page.text, "og:title")
        # og:title usually ends " | Site name"; the post needs the article's own title.
        title = title.rsplit(" | ", 1)[0] if " | " in title else title
        found.append({"slug": path.rstrip("/").rsplit("/", 1)[-1], "url": url, "date": date,
                      "title": title,
                      "description": meta(page.text, "og:description")
                      or meta(page.text, "description")})
    return sorted(found, key=lambda p: (p["date"], p["slug"]))


# ── post files ─────────────────────────────────────────────────────────

def read_post(path: Path) -> dict:
    md = path.read_text(encoding="utf-8")
    if not md.startswith("---"):
        return {"path": path, "error": "no frontmatter block"}
    _, head, body = md.split("---", 2)
    post = {"path": path, "text": body.strip()}
    for line in head.splitlines():
        m = re.match(r"^([A-Za-z_]+):\s*(.*?)\s*$", line)
        if m:
            value = m.group(2)
            if value[:1] == "'" and value[-1:] == "'":
                value = value[1:-1].replace("''", "'")
            post[m.group(1)] = value
    return post


def write_post(path: Path, fields: dict, text: str) -> None:
    def quote(v: str) -> str:
        return "'" + str(v).replace("'", "''") + "'"
    head = "\n".join(f"{k}: {quote(v)}" for k, v in fields.items())
    path.write_text(f"---\n{head}\n---\n{text.strip()}\n", encoding="utf-8")


def all_posts() -> list[dict]:
    return [read_post(p) for p in sorted(POSTS_DIR.glob("*.md"))]


def image_ok(path: Path) -> str:
    """'' if the file is a JPG or PNG Google will take, else what is wrong."""
    if not path.is_file():
        return f"{path.relative_to(ROOT)} does not exist (run `gbp_post.py image`)"
    data = path.read_bytes()
    if not (data[:3] == b"\xff\xd8\xff" or data[:8] == b"\x89PNG\r\n\x1a\n"):
        return f"{path.name} is not a JPG or PNG"
    if len(data) < MIN_IMAGE_BYTES:
        return f"{path.name} is {len(data)} bytes; Google needs at least {MIN_IMAGE_BYTES}"
    return ""


def problems(post: dict, online: bool = True) -> list[str]:
    if "error" in post:
        return [post["error"]]
    errors = []
    text = post.get("text", "")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", post.get("publish_on", "")):
        errors.append("publish_on must be a YYYY-MM-DD date")
    if not (MIN_CHARS <= len(text) <= MAX_CHARS):
        errors.append(f"the text is {len(text)} characters; it must be {MIN_CHARS} to {MAX_CHARS}")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if re.search(r"\[(HOOK|SUMMARY)\b", text):
        errors.append("the caption still has a [HOOK] or [SUMMARY] placeholder")
    elif len(paragraphs) < 3:
        errors.append("the caption needs a hook, a summary and a call to action, "
                      "as separate paragraphs")
    else:
        if len(paragraphs[0]) > MAX_HOOK_CHARS:
            errors.append(f"the hook (first paragraph) is {len(paragraphs[0])} characters; "
                          f"keep it to {MAX_HOOK_CHARS}")
        if BUTTON_LABEL.lower() not in paragraphs[-1].lower():
            errors.append(f"the last paragraph should be the call to action and mention "
                          f"the {BUTTON_LABEL!r} button")
    if "\u2026" in text or "..." in text:
        errors.append("the text contains an ellipsis: is it a cut-off description?")
    for pattern, what in BANNED:
        hit = pattern.search(text)
        if hit:
            errors.append(f"the text contains {what}: {hit.group(0)!r}")
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
    if post.get("image"):
        problem = image_ok(IMAGES_DIR / post["image"])
        if problem:
            errors.append(problem)
    else:
        errors.append("image is missing")
    return errors


def is_public_photo(url: str) -> bool:
    try:
        r = requests.head(url, timeout=20, allow_redirects=True)
    except requests.RequestException:
        return False
    return r.status_code == 200 and r.headers.get("Content-Type", "").startswith(
        ("image/jpeg", "image/png"))


# ── Business Profile API ───────────────────────────────────────────────

def have_credentials() -> bool:
    return all(os.environ.get(k, "").strip() for k in (
        "GBP_CLIENT_ID", "GBP_CLIENT_SECRET", "GBP_REFRESH_TOKEN",
        "GBP_ACCOUNT_ID", "GBP_LOCATION_ID"))


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


def posted_links(posts: list[dict]) -> set[str]:
    return {(p.get("callToAction") or {}).get("url", "").rstrip("/") for p in posts} - {""}


# ── commands ───────────────────────────────────────────────────────────

def cmd_prepare(args) -> None:
    since = os.environ.get("GBP_POST_SINCE", "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", since):
        fail("GBP_POST_SINCE must be a YYYY-MM-DD date, so older insights are not posted")
    insights = site_insights(since)
    print(f"{len(insights)} insight(s) under {PATH_PREFIX} dated {since} or later")

    # Already handled: a post file on this branch, a post/<slug> branch awaiting
    # review, or a post on the profile linking to the insight.
    have = {p.get("cta_url", "").rstrip("/") for p in all_posts()}
    branches = subprocess.run(["git", "ls-remote", "--heads", "origin", "post/*"], cwd=ROOT,
                              capture_output=True, text=True)
    if branches.returncode != 0:
        fail(f"Listing post/ branches failed: {branches.stderr.strip()[:300]}")
    pending = {line.rsplit("refs/heads/post/", 1)[-1] for line in branches.stdout.splitlines()}
    if have_credentials():
        have |= posted_links(existing_posts(*api()))
    else:
        print("  (no Business Profile credentials: not checking the profile's own posts)")

    made = 0
    for insight in insights:
        if made >= args.limit:
            break
        if insight["url"] in have or insight["slug"] in pending:
            continue
        today = dt.date.today().isoformat()
        path = POSTS_DIR / f"{today}-{insight['slug']}.md"
        write_post(path, {"publish_on": today, "cta_url": insight["url"],
                          "article_date": insight["date"], "image": f"{insight['slug']}.jpg",
                          "image_prompt": "", "insight_title": insight["title"],
                          "insight_description": insight["description"]},
                   f"{HOOK_PLACEHOLDER}\n\n{SUMMARY_PLACEHOLDER}\n\n{CTA_TEXT}")
        print(f"PREPARED {path.relative_to(ROOT)}  (branch: post/{insight['slug']})")
        made += 1
    if made == 0:
        print("nothing new to prepare")


def cmd_image(args) -> None:
    path = Path(args.file)
    post = read_post(path)
    prompt = post.get("image_prompt", "").strip()
    if not prompt:
        fail(f"{path.name} has no image_prompt; write one from the insight first")
    if not post.get("image"):
        fail(f"{path.name} has no image filename")
    if STYLE_FILE.is_file():
        prompt = f"{prompt}\n\n{STYLE_FILE.read_text(encoding='utf-8').strip()}"
    else:
        print(f"  warning: {STYLE_FILE.relative_to(ROOT)} is missing; no brand style applied",
              file=sys.stderr)
    r = requests.post(OPENAI_API, timeout=300,
                      headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"},
                      json={"model": IMAGE_MODEL, "prompt": prompt, "size": IMAGE_SIZE,
                            "output_format": "jpeg", "n": 1})
    if r.status_code != 200:
        fail(f"OpenAI image generation failed ({r.status_code}): {r.text[:300]}")
    data = r.json()["data"][0]
    raw = (base64.b64decode(data["b64_json"]) if data.get("b64_json")
           else requests.get(data["url"], timeout=120).content)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    out = IMAGES_DIR / post["image"]
    out.write_bytes(raw)
    problem = image_ok(out)
    if problem:
        fail(problem)
    print(f"  wrote {out.relative_to(ROOT)} ({len(raw)} bytes, {IMAGE_MODEL})")


def cmd_check(args) -> None:
    worst = 0
    for name in args.files:
        post = read_post(Path(name))
        errors = problems(post)
        print(f"{'FAIL' if errors else 'ok'}  {name}  ({len(post.get('text', ''))} characters)")
        for e in errors:
            print(f"  error: {e}")
        worst = max(worst, 1 if errors else 0)
    sys.exit(worst)


def cmd_list(args) -> None:
    posts = existing_posts(*api())
    print(f"{len(posts)} post(s) on the profile, newest first")
    for p in sorted(posts, key=lambda p: p.get("createTime", ""), reverse=True):
        link = (p.get("callToAction") or {}).get("url", "")
        photo = "photo" if p.get("media") else "no photo"
        print(f"- {p.get('createTime', '')[:10]}  {p.get('state', '')}  {photo}  {link}")
        summary = re.sub(r"\s+", " ", p.get("summary", ""))
        print(f"  {summary[:160]}")


def cmd_publish(args) -> None:
    today = dt.date.today().isoformat()
    due = sorted((p for p in all_posts() if p.get("publish_on", "9999") <= today),
                 key=lambda p: (p["publish_on"], p["path"].name))
    print(f"{len(due)} approved post(s) due on or before {today}")

    if args.dry_run and not have_credentials():
        print("  (no Business Profile credentials: skipping the check against existing posts)")
        url, headers, done = "", {}, set()
    else:
        url, headers = api()
        done = posted_links(existing_posts(url, headers))

    made = 0
    for post in due:
        if made >= args.limit:
            break
        if post.get("cta_url", "").rstrip("/") in done:
            continue
        name = post["path"].name
        # Checked only now, so an old post whose link has since died does not
        # block new ones. An approved post that fails is for a person to fix:
        # it is reported, never skipped silently.
        errors = problems(post)
        if errors:
            fail(f"{name} is approved but does not pass check: {'; '.join(errors)}")
        photo = IMAGE_BASE + post["image"]
        if not is_public_photo(photo):
            fail(f"{name}: Google could not fetch its image at {photo}. The image has to be "
                 "public: is this repository public, and is the post merged into main?")
        body = {"languageCode": "en-GB", "summary": post["text"], "topicType": "STANDARD",
                "callToAction": {"actionType": "LEARN_MORE", "url": post["cta_url"]},
                "media": [{"mediaFormat": "PHOTO", "sourceUrl": photo}]}
        if args.dry_run:
            print(f"  would post {name}: {body}")
            made += 1
            continue
        r = requests.post(url, headers=headers, json=body, timeout=60)
        if r.status_code != 200:
            fail(f"Posting {name} to the Business Profile failed ({r.status_code}): {r.text[:300]}")
        search_url = r.json().get("searchUrl", "")
        print(f"  posted {name} -> {search_url or r.json().get('name', '')}")
        message = {"event": "gbp_posted", "client": SITE_NAME, "file": name,
                   "post_url": search_url, "cta_url": post["cta_url"]}
        message.update(teams_card(
            f"Posted to the {SITE_NAME} Business Profile",
            [("Insight", post["cta_url"]), ("Image", photo)],
            body=post["text"],
            link=("See the post on Google", search_url) if search_url
            else ("Open the insight", post["cta_url"])))
        send(message)
        made += 1

    if made == 0:
        print("nothing new to post")


def cmd_notify_pr(args) -> None:
    post = read_post(Path(args.file))
    message = {"event": "gbp_post_drafted", "client": SITE_NAME, "pr_url": args.pr_url,
               "file": Path(args.file).name}
    message.update(teams_card(
        f"{SITE_NAME} Business Profile post ready for review",
        [("Insight", post.get("cta_url", "")),
         ("Goes live", "at the first daily run after merging"),
         ("Image", "see Files changed in the pull request")],
        body=post.get("text", ""),
        link=("Review the post and its image", args.pr_url)))
    if send(message):
        print("  Teams notification sent")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("prepare", help="draft a post for the next new insight")
    s.add_argument("--limit", type=int, default=1)
    s.set_defaults(func=cmd_prepare)
    i = sub.add_parser("image", help="generate a post's image from its image_prompt")
    i.add_argument("file")
    i.set_defaults(func=cmd_image)
    c = sub.add_parser("check", help="validate post files")
    c.add_argument("files", nargs="+")
    c.set_defaults(func=cmd_check)
    lst = sub.add_parser("list", help="show the posts already on the profile")
    lst.set_defaults(func=cmd_list)
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
