---
name: gbp-insight-image
description: Write the caption (hook, summary, call to action) and the image_prompt for a Rothian insight's Business Profile post, generate the image, and look at it before the pull request. Use whenever a post file in posts/ has been prepared.
---

# The caption and image for an insight post

`gbp_post.py prepare` writes the post file with the insight's title and
description in the frontmatter (`insight_title`, `insight_description`) and a
caption to fill in:

    [HOOK: ...]

    [SUMMARY: ...]

    Read the full insight on our website, using the Learn more button below.

You replace the two placeholders and write the image prompt. `check` fails
while a placeholder is left.

## Read the insight first

Open the insight's page (`cta_url`) and read the whole of it, not just the
title. Find the one concrete thing it is about: the mechanism, the failure, the
before and after, and what a reader should do about it. Both the caption and
the picture come from that.

## The caption

Three paragraphs, separated by blank lines. Start from the insight's own title
and description, then sharpen them.

1. **Hook** (one line, 150 characters at most). Google shows only the first
   line or two before "More", so this decides whether anyone reads on. Give
   the sharpest true point of the insight: a counter-intuitive claim, a
   consequence or a direct question to a B2B buyer. "Buying an ad in ChatGPT
   won't make ChatGPT recommend you." works; "Exciting news in AI!" does not.
2. **Summary** (two or three sentences, about 250 to 450 characters). What
   happened and why it matters to the reader's business, based on the insight's
   title and description. Plain and specific, with facts only from the insight.
3. **Call to action** (one line). Keep the default, or make it more specific
   to what the article offers ("Read the six steps we would take in the full
   insight, using the Learn more button below."). It must mention the **Learn
   more** button, which carries the link. The caption is plain text and the
   button sits underneath it, so point the reader down to the button ("below")
   rather than writing "tap Learn more", which reads like a link that does
   nothing.

Rules:

- British English, Rothian's calm and expert voice: no hype, no exclamation
  marks, no emoji, no hashtags, no links, phone numbers or email addresses
  (`check` rejects these).
- No relative dates such as "this month" or "next week": the post may go out
  days after the article was written. Name the month or leave the time out.
- Do not claim anything the article does not say.
- Keep the whole caption under about 750 characters.

## The image

Every image gets the same Rothian look: `gbp_post.py image` appends the house
style in `brand/image-style.txt` (a dark background, cream and navy forms,
red and orange accents, a clean editorial 3D finish) to your prompt. So the
prompt describes only **what is in the picture**. Change the house style
only in that file, never per post.

Write it in the post's frontmatter as `image_prompt`, one paragraph, single
quoted (double any apostrophe inside it: `isn''t`).

- **Build the scene from AI, technology, cybersecurity and business objects**:
  screens and interfaces, chat windows, servers, cloud and network nodes, data
  flowing between systems, dashboards and charts without figures, locks, keys,
  shields and access gates, documents, pipelines, an office desk or meeting
  table. Pick the objects that show the insight's mechanism.
- **Be specific to the insight.** A prompt that could belong to any insight
  produces a picture that belongs to none of them. "Data security" is not a
  subject. "An AI agent reaching past a locked dashboard into a table where
  every row carries its own small padlock" is.
- **Two to four concrete elements**, saying what each is, where it is and what
  it is doing. Keep the main subject central and large: Business Profile may
  trim the sides.
- **No text, no numbers, no logos, no brand names, no real people.** Image
  models misspell words and invent figures. Show people, if at all, as hands or
  figures without visible faces. Avoid keyboards and close-up labels, which
  attract fake lettering. End the prompt with "No text, no numbers, no logos."
- **No style words** (colours, lighting, medium, "photorealistic",
  "isometric"): the house style supplies them, and conflicting words break the
  consistency.
- **Nothing alarming for its own sake**: no hooded hackers, skulls or
  dripping-code clichés for a security insight. Show the mechanism.

## Generate and look

    python3 gbp_post.py image posts/<file>.md

It writes `posts/images/<slug>.jpg`. Then open the file and look at it:

- Does it show what the insight is about? Would someone who read the hook see
  the connection?
- Does it look like the house style: dark background, cream and navy, red or
  orange accent, clean and professional? Would it sit well beside the previous
  posts?
- Is there any text, number, logo or mangled lettering? Any real person?
- Is the subject large and central, and whole?

If any answer is wrong, change the prompt and generate again. Three attempts
at most; if the third still fails, open the pull request anyway and say what is
wrong with the image in its body, so the reviewer can decide.

Then run `python3 gbp_post.py check posts/<file>.md`; it must pass.
