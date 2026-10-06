# Durga Puja knowledge articles

Every `.md` file here becomes a page on https://pujoparikramaguide.in/ at deploy, built by `scripts/build_seo.py`:
plain HTML with structured data, listed in the sitemap and in `llms.txt`.
The file's path mirrors its URL:
`content/knowledge/durga-puja/rituals/ashtami.md` → `/durga-puja/rituals/ashtami/`, and
`content/knowledge/navratri/index.md` → `/navratri/`.

## File format

TOML front matter between `+++` lines, then the article body in Markdown.

```
+++
title = "Maha Ashtami: Pushpanjali, Kumari Puja and Sandhi Puja | Pujo Parikrama"   # <title>, 45–65 characters before the " | Pujo Parikrama"
description = "What happens on Maha Ashtami of Durga Puja: …"                       # meta description, 140–160 characters
h1 = "Maha Ashtami: the heart of Durga Puja"
summary = """Two to four plain sentences that answer the page's main question on their own: an AI answer
engine should be able to quote this paragraph and be right. Name the thing, say what it is, when, and why."""
type = "Article"            # "Article"; "HowTo" for step-by-step pages (add [[steps]]); "Recipe" for recipes (see below)
section = "Rituals"         # the hub it's listed under: "Durga Puja", "Rituals", "At home", "Recipes", "Navratri", "Festivals", "Culture", "Visit"
order = 40                  # sort order inside its section
keywords = ["Maha Ashtami", "Durga Ashtami", "Sandhi Puja", "Kumari Puja"]
related = ["durga-puja/rituals/sandhi-puja/", "durga-puja/rituals/kumari-puja/"]   # other article paths
places = ["bagbazar", "sovabazar_rajbari"]   # optional: Kolkata pandal ids (app/data/guide.json) worth visiting for this
image = "pushpanjali"       # the photo at the top, and the article's share picture (a key in photos.toml)
images = ["kumari-puja", "sandhi-puja"]   # optional: photos placed between sections as the article goes on

[[faq]]                     # 4–6 real questions people search; answers 1–3 sentences, plain text
q = "What time is Sandhi Puja on Ashtami 2026?"
a = "…"

[[sources]]                 # 1–4 well-known, stable references only (Wikipedia, UNESCO, Britannica, government sites)
name = "Durga Puja, Wikipedia"
url = "https://en.wikipedia.org/wiki/Durga_Puja"

# HowTo pages only:
total_time = "PT2H"         # ISO 8601 duration
supplies = ["Kalash (copper or brass pot)", "Mango leaves", "…"]
[[steps]]
name = "Clean and prepare the space"
text = "…"
+++

Markdown body…
```

## Recipes

`type = "Recipe"` pages also need the following. The method goes in `[[steps]]`; the body holds the story, tips and variations.

```
recipe_yield = "4 servings"
prep_time = "PT15M"
cook_time = "PT45M"
recipe_category = "Bhog"          # or "Sweet", "Snack", "Main course"
recipe_cuisine = "Bengali"
diet = "Vegetarian"               # "Vegetarian", "Vegan" or "" (only if true for the recipe as written)
ingredients = ["1 cup gobindobhog rice", "½ cup yellow moong dal, dry-roasted", "…"]
[[steps]]
name = "Roast the dal"
text = "…"
```

## Markdown that the builder understands

- `## Heading` and `### Subheading`. The page's h1 comes from front matter; never use `#` in the body.
- Paragraphs, `**bold**`, `*italic*`, `- bullet` lists and `1. numbered` lists.
- Links: `[text](/durga-puja/history/)` for pages on this site, always starting with `/`, or a full `https://…` URL for
  anything elsewhere.
- Tables made of `| a | b |` rows; the second row is `|---|---|`.
- `> quote` lines, for mantras and verses. Give the original (Sanskrit or Bengali), then a transliteration, then a meaning.
- `- [ ] item` makes a tick-box checklist; readers' ticks are saved on their own phone (use it for packing and samagri lists).
- A `>` quote containing Bengali or Devanagari becomes a mantra block, with Copy and WhatsApp buttons.
- `> **Tip:** …` makes a callout box. Also `**Note:**`, `**Did you know?**`, `**Good to know:**`, `**Remember:**`, `**Etiquette:**`
  and `**Safety:**`.
- `![Caption](photo:key)` on its own line places a photo from `photos.toml` exactly there. Usually `images` in the front
  matter is enough: those photos are spread between the sections automatically.
- No raw HTML and no `#` headings.

## Photos

Photos come from Wikimedia Commons, under free licences only (CC0, public domain, CC BY, CC BY-SA; never NC or ND), and are
credited under each photo. `photos.toml` lists them. To add one:

1. Add a `[key]` with `q = ["search words", …]`, then run **Actions → article-photos** with `mode=candidates`. A numbered
   contact sheet appears in `data/photo_candidates/<key>.jpg`.
2. Copy the chosen file's title from `<key>.json` into `file = "File:…"`, and write a `caption` that says what the photo shows.
3. Run the workflow with `mode=fetch`. It saves `app/img/guide/<key>.webp` (1,200 px) and `<key>-600.webp`, records the
   credit in `photos.json`, and clears the contact sheets.

## Writing rules

1. **Answer first.** The `summary` and the first paragraph answer the question in the title.
2. **Accurate and honest.**
   - Don't invent dates, numbers, names, quotations or statistics.
   - Rituals vary by family, region and panjika (almanac). Say so, rather than presenting one practice as universal.
   - Give exact muhurta (auspicious) timings only from the 2026 dates below. Otherwise say "check your local panjika".
3. **Original text.** Write your own words; don't copy from any source.
4. **Respectful.** This is a living religious tradition. Describe practices, don't rank them, and avoid stereotypes.
5. **Useful.** Concrete details: what happens, who does it, what you'll see, what to wear, what to bring, the words people
   say. Explain Bengali and Sanskrit terms the first time they appear (*bodhon*, awakening).
6. **Linked.** Link to related articles and to the Kolkata guide where it helps:
   - `/guide/` and `/guide/dates/`;
   - `/guide/areas/<zone>/`;
   - `/guide/pandals/<id>/`;
   - `/guide/trails/<id>/`.
7. **Length.** 700–1,400 words in the body for full articles, 400–800 for short ritual pages.

## Durga Puja 2026 dates (the only dates to state as fact)

Mahalaya: Saturday 10 October 2026. Panchami: Friday 16 October. Shashthi: Saturday 17 October.
Saptami: Sunday 18 October. Maha Ashtami: Monday 19 October. Maha Navami: Tuesday 20 October.
Bijoya Dashami: Wednesday 21 October 2026.

## Photo stories

`stories.toml` holds the photo stories: Google Web Stories (AMP) published at `/stories/<slug>/` and listed at `/stories/`,
in the sitemap and on the guide they retell. Each `[[story]]` has a `slug`, `title`, `dek`, the `article` it links to, a `cover`
photo and 5–9 `[[story.pages]]` (`image`, optional `kicker`, `heading`, about 25 words of `text`, optional `link`). Only say
what the guide itself says. Every other guide gets a story made automatically from its own text (each step, or each
section's heading and opening sentence), with photos matched to the topic and music by section; write one in
`stories.toml` to replace it. **Actions → story-check** validates every story as AMP and commits phone screenshots to
`data/story_screens/` for review.
