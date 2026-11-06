# Routines

Two routines share one environment:

| Routine | When | What it does |
|---|---|---|
| **Writer** | weekly | Drafts one post in `posts/`, opens a draft pull request, tells Teams |
| **Publisher** | daily | Posts approved (merged) posts that are due, at most one per run |

Merging the writer's pull request is the approval. Nothing reaches the profile
without it: the publisher reads `main` only.

## Environment

Create one environment, for example `Rothian GBP`.

**Variables** (plain text):

```
GBP_ACCOUNT_ID=116592847110487137624
GBP_LOCATION_ID=17962375305605091292
GBP_SITE_NAME=Rothian
GBP_LINK_PREFIX=https://www.rothian.com/
GBP_DRY_RUN=true
```

`GBP_LOCATION_ID` is the verified `https://www.rothian.com` profile. Keep
`GBP_DRY_RUN=true` until the publisher's first dry run has been checked, then
set it to `false`.

**API credentials** (secrets, never in the variables box):

```
GBP_CLIENT_ID=...
GBP_CLIENT_SECRET=...
GBP_REFRESH_TOKEN=...
POWERAUTOMATE_WEBHOOK_URL=...
```

The first three come from the Google Cloud project's Desktop app client and from
running `gbp_auth.py` once (see README.md).

**Network policy:** allow `oauth2.googleapis.com`, `mybusiness.googleapis.com`,
`www.rothian.com`, the Teams webhook's host, and PyPI if not already allowed.

**Setup script:**

```bash
#!/bin/bash
# No set -e: a failed install is retried by the routine after checkout.
set -uo pipefail
python3 -m pip install --quiet --disable-pip-version-check requests \
  && echo "ok: requests" \
  || echo "WARN: pip install failed; the routine should retry it"
```

---

## Writer (weekly)

- **Repository:** `Rothian-ai/rothian-gbp`
- **Trigger:** weekly, for example Monday 09:07 local time
- **Environment:** the one above

Instructions:

```
Draft ONE Google Business Profile post for Rothian and open it as a DRAFT pull
request for review. Never post to Google yourself and never merge: the
publisher routine posts it once a person merges the pull request.

1. Run: pip install -r requirements.txt
2. Read .claude/skills/gbp-post-writing/SKILL.md and follow it. Do not work
   from memory.
3. See what exists: list posts/ on main and read the most recent files, then
   run `python3 gbp_post.py list` for what is already live on the profile.
   Also list open pull requests on this repository with the GitHub MCP tools
   and read any post still awaiting review, so this week's post does not repeat
   it. Pick the topic kind used least recently, and a subject not yet covered.
4. Open the rothian.com page(s) the post will draw on and read them. Every fact
   in the post must be on those pages.
5. Write posts/<publish_on>-<short-slug>.md, with publish_on set to tomorrow.
6. Run `python3 gbp_post.py check posts/<file>.md` and fix every error.
7. Create a branch post/<short-slug>, commit only that file with
   `git -c commit.gpgsign=false commit`, and push it. Open a DRAFT pull request
   against main with the GitHub MCP tools: title "GBP post: <first few words>",
   body containing the full post text, the topic, the button URL and the
   source pages you used.
8. Run `python3 gbp_post.py notify-pr <PR URL> posts/<file>.md` to send the
   post to Teams for review.

If any step fails, do not open a half-finished pull request. Post
{"event":"run_failed","reason":"<what failed>"} to POWERAUTOMATE_WEBHOOK_URL
and stop.

Deliver: the pull request URL, the topic, and the post text.
```

## Publisher (daily)

- **Repository:** `Rothian-ai/rothian-gbp`
- **Trigger:** daily, for example 10:07 local time
- **Environment:** the same one

Instructions:

```
Publish approved Rothian Business Profile posts. A post is public immediately,
so gbp_post.py is the only thing that posts: never call the Business Profile
API yourself, and never edit or create post files in this routine.

1. Run: pip install -r requirements.txt
2. Make sure the checkout is main and up to date: git checkout main && git pull
3. If the variable GBP_DRY_RUN is "true", run
       python3 gbp_post.py publish --dry-run
   and send a notification with its full output so it can be checked before
   GBP_DRY_RUN is set to "false". Then stop.
4. Otherwise run: python3 gbp_post.py publish
   It posts at most one approved post that is due and not already on the
   profile, and sends the Teams message itself.
5. If it prints "nothing new to post", stop quietly. That is the normal result
   on most days and needs no notification.
6. If it exits non-zero it has already posted {"event":"run_failed"} to Teams.
   Do not retry. Send a notification with the error it printed and stop. An
   error mentioning invalid_grant means gbp_auth.py must be run again and the
   new GBP_REFRESH_TOKEN saved in the environment.

Commit nothing.
```
