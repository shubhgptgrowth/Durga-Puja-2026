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
type = "Article"            # "Article", or "HowTo" for step-by-step pages (then add [[steps]] below)
section = "Rituals"         # the hub it's listed under: "Durga Puja", "Rituals", "At home", "Navratri", "Culture"
order = 40                  # sort order inside its section
keywords = ["Maha Ashtami", "Durga Ashtami", "Sandhi Puja", "Kumari Puja"]
related = ["durga-puja/rituals/sandhi-puja/", "durga-puja/rituals/kumari-puja/"]   # other article paths
places = ["bagbazar", "sovabazar_rajbari"]   # optional: Kolkata pandal ids (app/data/guide.json) worth visiting for this

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

## Markdown that the builder understands

- `## Heading` and `### Subheading`. The page's h1 comes from front matter; never use `#` in the body.
- Paragraphs, `**bold**`, `*italic*`, `- bullet` lists and `1. numbered` lists.
- Links: `[text](/durga-puja/history/)` for pages on this site, always starting with `/`, or a full `https://…` URL for
  anything elsewhere.
- Tables made of `| a | b |` rows; the second row is `|---|---|`.
- `> quote` lines, for mantras and verses. Give the original (Sanskrit or Bengali), then a transliteration, then a meaning.
- No raw HTML, no images, no `#` headings.

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
