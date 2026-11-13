# rothian-gbp

Shares each new insight from rothian.com/insights on Rothian's Google Business
Profile, with an illustration generated for it, after a person approves it.

```
Daily routine                         You                       Daily routine (next run)
finds the next new insight            look at the post and      posts it to the profile
writes hook, summary and CTA          its image in the PR,      with the image, and
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
| `.claude/skills/gbp-insight-image/SKILL.md` | How the caption and the image prompt are written and checked |
| `brand/image-style.txt` | Rothian's house image style, added to every image prompt |
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

## The caption and the image

Each caption has three paragraphs: a one-line **hook** (Google shows only the
first lines before "More"), a short **summary** drawn from the insight's title
and description, and a **call to action** pointing at the Learn more button,
which links to the insight. Its default wording is set by `GBP_CTA_TEXT`.

Every image is generated with the same house style, `brand/image-style.txt`,
taken from rothian.com's colours: a dark background, cream and navy forms, and
red and orange accents. Edit that file to change the look of all future posts;
the per-post `image_prompt` describes only what is in the picture.

## What `check` enforces

- 80 to 1,500 characters of text.
- A hook of at most 150 characters, a summary, and a last paragraph that
  mentions the Learn more button; no `[HOOK]`/`[SUMMARY]` placeholder and no
  ellipsis left from a cut-off description.
- No phone numbers, email addresses, social handles, links or hashtags in the
  text: Google may remove posts with unverified contact details, and the
  button carries the link.
- The button links to a live rothian.com page.
- The image exists and is a JPG or PNG of at least 10 KB.

`publish` also refuses to post if Google could not fetch the image from its
public URL.
