---
name: gbp-post-writing
description: Write one Google Business Profile post for Rothian as a markdown file in posts/, in Rothian's voice, from facts on rothian.com. Use when drafting or editing a Business Profile post.
---

# Writing a Rothian Business Profile post

A Business Profile post appears on Rothian's listing in Google Search and Maps,
next to the reviews and the opening hours. The reader is someone who has just
searched for Rothian or for the kind of work Rothian does. They give it a few
seconds. The post has to tell them one useful, specific thing and give them one
place to go next.

It is not a blog post, not an advert, and not a summary of the website.

## The file

One post is one file: `posts/<publish_on>-<short-slug>.md`.

```markdown
---
publish_on: '2026-11-10'
topic: case-study
cta_url: https://www.rothian.com/case-studies/telecoms-ransomware-and-apt
---
The text of the post.
```

- `publish_on`: the day after the routine runs, so a reviewer has time. The
  post goes out on that date or when the pull request is merged, whichever is
  later.
- `topic`: `service`, `case-study`, `insight` or `news` (see the mix below).
- `cta_url`: the one rothian.com page the post leads to. It becomes the "Learn
  more" button. It must be the most specific page that continues the post, never
  the homepage when a better page exists.
- `cta`: leave it out (it defaults to `LEARN_MORE`). `BOOK` or `SIGN_UP` only if
  the page is a booking or sign-up page.
- `image`: leave it out for now. Posts are text only until images are agreed.

Run `python3 gbp_post.py check posts/<file>.md` and fix every error before
committing. Warnings are for the reviewer; fix them unless there is a reason.

## The mix

Rotate through four kinds, so the profile does not read as one note repeated.
Read the last few files in `posts/` and the output of `python3 gbp_post.py list`
(what is already live), then pick the kind used least recently.

| Topic | What it is | Where the facts come from | Button goes to |
|---|---|---|---|
| `case-study` | One engagement: the situation, what Rothian did, what changed | The case study page itself | That case study |
| `service` | One capability or service, framed as the problem it solves | That capability's page (/cloud, /cyber, /data, /digital, /design, /development, /strategy, /ui4ai, /ai-agents, /solutions, /delivery-framework) | That page |
| `insight` | One idea from a Rothian insight, stated plainly | The insight page on rothian.com/insights | That insight |
| `news` | Something new at Rothian: a new insight series, a new case study, a new solution, an update | rothian.com/updates, /insights, /case-studies | The page announcing it |

`news` needs something actually new. If nothing has changed since the last
`news` post, take the next kind instead. Never invent news.

Do not repeat a subject already posted (compare with `posts/` and the live
list): a different case study, capability or insight each time, until the set
is exhausted. Then a returning subject needs a genuinely different angle.

## Facts

Every fact in a post must be stated on the rothian.com page the button leads to,
or on another rothian.com page. Open the page and read it; do not work from
memory or from a search summary.

- No figures, client names, results or claims that the page does not state.
  If a case study does not name its client, neither does the post.
- No prices, discounts, guarantees or rankings.
- No forecasts, and nothing about competitors.
- No time words that age: "this week", "recently", "new" for something that
  will not stay new. A date is fine.

## Shape

Four short paragraphs at most, 300 to 1,500 characters (the checker enforces
this); 500 to 900 reads best.

1. **Open with the point**, not with Rothian. The first sentence is what shows
   in the preview before "More": make it the problem, the finding or the
   outcome. "A UK operator called about ransomware on a Friday night." Not
   "At Rothian, we are proud to...".
2. **One or two sentences of substance**: what happened, what Rothian did, or
   why it matters, in concrete terms taken from the page.
3. **A closing line that leads to the button**, without saying "click": the
   reader should want the rest of the story. No "contact us today".

## Voice

Rothian's site speaks plainly and with confidence, in short declarative
sentences: "We deliver outcomes, not resources." "Bring us the problem, not a
role specification." Write like that.

- Plain words. No "leverage", "unlock", "cutting-edge", "game-changer",
  "seamless", "solutions" as a filler noun, "in today's fast-paced world".
- British spelling: organisation, programme, analyse, centre, defence.
- Vary sentence length. A short sentence after a longer one.
- No exclamation marks, no emojis, no hashtags, no em dashes, no capitals for
  emphasis.
- Say "we" for Rothian, sparingly. The subject is the reader's problem.

## What Google removes

The checker refuses these, because Google may remove a post that carries them
or ignores them:

- phone numbers, email addresses and social handles in the text ("we may remove
  posts with unverified contact information"): the profile already shows the
  contact details, and the button does the rest;
- links in the text (they are not clickable; the button carries the link);
- hashtags.

Also keep within Google's content policies: nothing misleading, offensive or
off-topic, and nothing about regulated products.
