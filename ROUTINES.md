# Routine

One daily routine does both halves of the job:

1. **Publish** any approved post that is not on the profile yet (one per run).
2. **Prepare** the next new rothian.com insight: copy its title and
   description, generate an image, and open a draft pull request for review.

Merging the pull request is the approval. It also puts the image on `main`,
which is where Google fetches it from, so a post can only go out after a person
has merged it.

**This repository has to be public** for that to work. Google takes a post's
image only as a public URL, and the images are served from `main` through
`raw.githubusercontent.com`. The repository holds code, text copied from
rothian.com and images that become public on Google anyway; the secrets live in
the routine environment, never in the repository. To host the images somewhere
else instead, set `GBP_IMAGE_BASE_URL` to a public address that serves
`posts/images/` from `main`.

## Environment

Create one environment, for example `Rothian GBP`.

**Variables** (plain text):

```
GBP_ACCOUNT_ID=116592847110487137624
GBP_LOCATION_ID=17962375305605091292
GBP_SITE_NAME=Rothian
GBP_SITEMAP_URL=https://www.rothian.com/sitemap.xml
GBP_PATH_PREFIX=/insights/
GBP_LINK_PREFIX=https://www.rothian.com/
GBP_POST_SINCE=2026-11-06
OPENAI_IMAGE_MODEL=gpt-image-1.5
GBP_DRY_RUN=true
```

- `GBP_LOCATION_ID` is the verified `https://www.rothian.com` profile.
- `GBP_POST_SINCE`: only insights published on or after this date are shared.
  Today's date shares only new insights; an earlier date works through the
  back catalogue, one insight a day, oldest first.
- `GBP_DRY_RUN=true` until the first dry run has been checked, then `false`.
  While it is `true`, nothing is posted to Google, but pull requests are still
  prepared, so you can review the first images.

**API credentials** (secrets, never in the variables box):

```
GBP_CLIENT_ID=...
GBP_CLIENT_SECRET=...
GBP_REFRESH_TOKEN=...
OPENAI_API_KEY=...
POWERAUTOMATE_WEBHOOK_URL=...
```

The first three come from the Google Cloud project's Desktop app client and from
running `gbp_auth.py` once (see README.md).

**Network policy:** allow `oauth2.googleapis.com`, `mybusiness.googleapis.com`,
`api.openai.com`, `www.rothian.com`, `raw.githubusercontent.com`, the Teams
webhook's host, and PyPI if not already allowed.

**Setup script:**

```bash
#!/bin/bash
# No set -e: a failed install is retried by the routine after checkout.
set -uo pipefail
python3 -m pip install --quiet --disable-pip-version-check requests \
  && echo "ok: requests" \
  || echo "WARN: pip install failed; the routine should retry it"
```

## The routine

- **Name:** Rothian: Business Profile posts
- **Repository:** `Rothian-ai/rothian-gbp`
- **Trigger:** daily, for example 10:07 local time
- **Environment:** the one above

Instructions:

```
Share Rothian's insights on its Google Business Profile: publish what has been
approved, then prepare the next insight for approval. A Business Profile post
is public immediately, so gbp_post.py is the only thing that posts: never call
the Business Profile API yourself, never merge a pull request, and never post
anything that has not been merged into main.

1. Run: pip install -r requirements.txt
   Then: git checkout main && git pull

PUBLISH
2. If the variable GBP_DRY_RUN is "true", run
       python3 gbp_post.py publish --dry-run
   and keep its full output for the notification at the end.
   Otherwise run
       python3 gbp_post.py publish
   It posts at most one approved post that is due and not already on the
   profile, and sends its own Teams message. "nothing new to post" is normal.
   If it exits non-zero, it has already reported the error to Teams: note the
   error and continue to PREPARE.

PREPARE
3. Run: python3 gbp_post.py prepare
   If it prints "nothing new to prepare", skip to the end.
   Otherwise it prints PREPARED <file> and the branch name to use.
4. Read .claude/skills/gbp-insight-image/SKILL.md and follow it: read the
   insight, write image_prompt into the post file, run
   `python3 gbp_post.py image <file>`, and look at the image before going on.
   Then extend the post's text into a short summary as the skill says; keep
   the insight's own title and description as its first two lines.
5. Run `python3 gbp_post.py check <file>`; it must pass.
6. Create the branch it named (post/<slug>), commit the post file and its image
   with `git -c commit.gpgsign=false commit`, and push. Open a DRAFT pull
   request against main with the GitHub MCP tools: title "GBP: <insight
   title>", body with the post text, the insight URL and the image prompt.
7. Run `python3 gbp_post.py notify-pr <PR URL> <file>`.

If a PREPARE step fails, do not open a half-finished pull request: post
{"event":"run_failed","reason":"<what failed>"} to POWERAUTOMATE_WEBHOOK_URL.

At the end, send a notification only if something needs a person: a pull
request to review, a publish error, or the dry-run output while GBP_DRY_RUN is
"true". On a day with nothing published and nothing prepared, stay silent.

An error mentioning invalid_grant means gbp_auth.py must be run again and the
new GBP_REFRESH_TOKEN saved in the environment.
```
