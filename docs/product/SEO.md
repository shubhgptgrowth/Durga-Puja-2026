# Search and AI answer engines (SEO, GEO, AEO)

The app is a JavaScript single-page app. Google can render it, but most AI crawlers (ChatGPT/GPTBot,
Claude, Perplexity, …) only read raw HTML, and would see an empty page. So every deploy also builds plain
HTML pages from `app/data/guide.json` (`scripts/build_seo.py`, run in `deploy.yml`; outputs are git-ignored).

| URL | What it answers |
|---|---|
| `/guide/` | Hub: what the guide covers, areas, most-visited pandals, trails, FAQ |
| `/guide/dates/` | "When is Durga Puja 2026?" Mahalaya to Dashami, with crowd levels |
| `/guide/areas/<zone>/` | "Best pandals in Gariahat / North Kolkata / …", food and parking there |
| `/guide/pandals/<id>/` | One per pandal (107): best time, quiet hours per day, metro, buses, parking, food, FAQ |
| `/guide/food/<id>/` | One per eatery (175): dishes, cost for two, veg/non-veg, hours, nearby pandals |
| `/guide/trails/<id>/` | The six ready-made walking routes, stop by stop |
| `/guide/parking/` | Park & ride and pay parking |
| `/sitemap.xml`, `/robots.txt` | Every page above; all crawlers, AI included, allowed |
| `/llms.txt`, `/llms-full.txt` | The [llms.txt](https://llmstxt.org) index, and the whole guide as one text file |

The home page also carries a plain-HTML summary with links, which the app removes as it starts.

## Built to be quoted (GEO / AEO)

- **The answer comes first.** Each page opens with a self-contained paragraph that names the place, the area and the
  dates, and gives the best time, the nearest metro and the walk. An answer engine can lift it as is.
- **Questions are headings.** Each page has an FAQ section ("What is the best time to visit …?", "How do I reach … by
  metro?"), also published as `FAQPage` structured data.
- **Facts carry their source.** Every page shows a "Last updated" date and labels crowd levels as estimates from the
  crowd model, not live counts. It also gives a "Cite as" line with the page's canonical URL.
- **Structured data (JSON-LD):**
  - pandal pages: `TouristAttraction` and `Event` (the 2026 dates, with geo coordinates)
  - eatery pages: `Restaurant` or `FoodEstablishment`
  - areas: `ItemList`
  - trails: `TouristTrip`
  - the hub: `WebSite` and `WebApplication`
  - every page: `BreadcrumbList`
- **Clean, stable URLs:** one canonical URL per page, in the sitemap with `lastmod`.
- **Photos credit their source:** Wikimedia Commons images keep their author and licence.

`tests/test_build_seo.py` checks every page in CI: title, description, canonical, a single h1, valid JSON-LD, links
that resolve, a sitemap that matches the files, and the crawler files. After each deploy, the `verify` job fetches
the live sitemap, `robots.txt`, `llms.txt` and guide pages.

## One-time: tell the search engines (about 10 minutes)

1. **Google Search Console** (<https://search.google.com/search-console>):
   - Add a property → **URL prefix** → `https://shubhgptgrowth.github.io/Durga-Puja-2026/`.
   - Choose **HTML tag** verification, and copy the `content="…"` value only.
   - Put that value in `site.json` as `"google_site_verification": "…"`, then push. The deploy adds the tag to every
     page. Click **Verify**.
   - **Sitemaps** → submit `sitemap.xml`.
   - Optional: **URL inspection** → `guide/` → **Request indexing**, to speed up the first crawl.
2. **Bing Webmaster Tools** (<https://www.bing.com/webmasters>):
   - **Import from Google Search Console**, one click. Bing's index feeds ChatGPT search and Microsoft Copilot,
     so this matters for AI answers too.

## Limits to know

- **robots.txt and llms.txt only count at the root of a domain.** The app lives under a path
  (`shubhgptgrowth.github.io/Durga-Puja-2026/`), so crawlers look for `shubhgptgrowth.github.io/robots.txt`
  instead. No such file exists, which means everything is allowed anyway. The sitemap still needs submitting by
  hand (step 1). A custom domain (HOSTING.md) puts both files where crawlers expect them; run
  `python scripts/site.py set https://your-domain/` and every canonical URL follows.
- **Pages are English.** Bengali names appear alongside, and the app itself is in English, Bengali and Hindi.
- **Indexing takes days to weeks.** Pandal pages have the best chance of ranking for long-tail searches like
  "<pandal> best time to visit" or "<pandal> nearest metro".
