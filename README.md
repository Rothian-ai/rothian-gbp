# rothian-gbp

Shares each new insight from rothian.com/insights on Rothian's Google Business
Profile, with an illustration generated for it, after a person approves it.

```
Daily routine                         You                       Daily routine (next run)
finds the next new insight            look at the post and      posts it to the profile
copies its title and description      its image in the PR,      with the image, and
generates an image (OpenAI)           then merge                tells Teams
opens a draft PR, tells Teams
```

A Business Profile post is public the moment it is made, so merging the pull
request is the approval: the routine only posts what is on `main`. Google takes
a post's image only as a public URL, and the images are served from `main`, so
**this repository must be public** (see ROUTINES.md).

Do not edit a published post on Google: change the post file in its pull
request before merging.

To skip an insight, close its pull request without merging and leave its
`post/<slug>` branch in place: the routine treats an existing branch as
handled. Deleting the branch puts the insight back in the queue.

## Files

| File | Purpose |
|---|---|
| `posts/` | One markdown file per post, images in `posts/images/` |
| `gbp_post.py` | `prepare`, `image`, `check`, `notify-pr`, `publish`, `list` |
| `gbp_auth.py` | One-time Google sign-in that produces the refresh token and IDs |
| `.claude/skills/gbp-insight-image/SKILL.md` | How the image prompt is written and checked |
| `ROUTINES.md` | Environment, setup script and the routine prompt |

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

Then set up the environment and the routine from `ROUTINES.md`.

## What `check` enforces

- 80 to 1,500 characters of text.
- No phone numbers, email addresses, social handles, links or hashtags in the
  text: Google may remove posts with unverified contact details, and the
  button carries the link.
- The button links to a live rothian.com page.
- The image exists and is a JPG or PNG of at least 10 KB.

`publish` also refuses to post if Google could not fetch the image from its
public URL.
