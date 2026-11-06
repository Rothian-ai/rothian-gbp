# rothian-gbp

Weekly posts for Rothian's Google Business Profile, written by a Claude routine,
approved by a person, and published by a second routine.

```
Writer routine (weekly)        You                    Publisher routine (daily)
drafts posts/<date>-<slug>.md  review the draft PR    posts merged, due posts
opens a draft PR, tells Teams  edit, then merge       to the profile, tells Teams
```

A Business Profile post is public the moment it is made, so merging the pull
request is the approval: the publisher only reads `main`. To change a post,
edit its file in the pull request before merging. Do not edit a published post
on Google: it would no longer match its file, and the publisher would post the
file again.

## Files

| File | Purpose |
|---|---|
| `posts/` | One markdown file per post (format in `gbp_post.py`) |
| `gbp_post.py` | `check` a draft, `list` live posts, `publish` approved posts, `notify-pr` Teams |
| `gbp_auth.py` | One-time Google sign-in that produces the refresh token and IDs |
| `.claude/skills/gbp-post-writing/SKILL.md` | The writing brief: mix, facts, shape, voice, Google's rules |
| `ROUTINES.md` | Environment, setup script, and both routine prompts |

## One-time Google setup

1. A Google Cloud project approved for the Business Profile APIs, with these
   enabled: Google My Business API, My Business Account Management API, My
   Business Business Information API.
2. Google Auth Platform: branding filled in, audience **External**, publishing
   status **In production** (in Testing the sign-in expires after 7 days).
3. A **Desktop app** OAuth client.
4. On your own computer, signed in as an owner or manager of the profile:

       python -m pip install requests
       python gbp_auth.py --client-id <id> --client-secret <secret>

   It prints the refresh token and the account and location IDs.

Then set up the environment and the two routines from `ROUTINES.md`.

## Checking a post by hand

    python3 gbp_post.py check posts/2026-11-10-example.md

It refuses phone numbers, email addresses, social handles, links and hashtags
in the text (Google may remove posts with unverified contact details), a text
outside 300 to 1,500 characters, and a button link that is not a live
rothian.com page. It warns about em dashes and exclamation marks.
