---
name: gbp-insight-image
description: Write the image_prompt for a Rothian insight's Business Profile post, generate the image, and look at it before the pull request. Use whenever a post file in posts/ needs its image.
---

# The image for an insight post

`gbp_post.py prepare` writes the post as the insight's own title and
description. That is too short for the profile, so after reading the insight
(below) extend the post text into a short summary, then write the picture.

## Extend the text

Keep the title line and the description paragraph exactly as they are, and add
after them, from the insight's own content only (no invented claims or figures):

- one short paragraph on what it means or why it matters;
- three to five short bullets ("• ...") of the key points or actions;
- an optional closing line pointing to the button.

Aim for 600 to 1,000 characters in total (hard limit 1,500). No links, phone
numbers, emails, @handles or hashtags: `check` rejects them, and the button
carries the link. Plain text only, no markdown.

## Read the insight first

Open the insight's page (`cta_url`) and read the whole of it, not just the
title. Find the one concrete thing it is about: the mechanism, the failure, the
before and after. The picture shows that thing.

A prompt that could belong to any insight produces a picture that belongs to
none of them. "Data security" is not a subject. "An agent reaching past a
locked dashboard into tables where every row carries its own lock" is.

## Write image_prompt

Put it in the post's frontmatter as `image_prompt`, one paragraph, single
quoted (double any apostrophe inside it: `isn''t`).

- **Describe only the subject and its arrangement**: what is in the picture,
  where, doing what. Two to four concrete elements.
- **Fill the frame.** Business Profile shows the image large and may trim the
  sides, so keep the main subject central and large, with nothing that matters
  near the left or right edge. Do not ask for empty bands or wide margins.
- **No text, no numbers, no logos, no brand names, no real people.** An image
  model misspells words and invents figures, and a real company's logo or a
  real person's likeness does not belong on Rothian's profile. End the prompt
  with "No text, no numbers, no logos."
- **Nothing about the look**: no colours, lighting, medium, style, mood or
  camera words ("photorealistic", "isometric", "cinematic", "minimalist",
  "blue tones"). Left alone, the model varies the treatment between posts, so
  the profile does not look stamped from one template.
- **Nothing alarming for its own sake**: no hooded hackers, skulls or
  dripping-code clichés for a security insight. Show the mechanism.

## Generate and look

    python3 gbp_post.py image posts/<file>.md

It writes `posts/images/<slug>.jpg`. Then open the file and look at it:

- Does it show what the insight is about? Would someone who read the title see
  the connection?
- Is there any text, number, logo or mangled lettering? Any real person?
- Is the subject large and central, and whole?

If any answer is wrong, change the prompt and generate again. Three attempts
at most; if the third still fails, open the pull request anyway and say what is
wrong with the image in its body, so the reviewer can decide.

Then run `python3 gbp_post.py check posts/<file>.md`; it must pass.
