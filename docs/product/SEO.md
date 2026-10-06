# Search and AI answer engines (SEO, GEO, AEO)

The app is a JavaScript single-page app. Google can render it, but most AI crawlers (ChatGPT/GPTBot,
Claude, Perplexity, …) only read raw HTML, and would see an empty page. So every deploy also builds plain
HTML pages from `app/data/guide.json` (`scripts/build_seo.py`, run in `deploy.yml`; outputs are git-ignored).

| URL | What it answers |
|---|---|
| `/durga-puja/` | **Knowledge hub**: what Durga Puja is, history, the goddess, rituals, at home, culture (`content/knowledge/`) |
| `/durga-puja/rituals/…` | Each day (Mahalaya → Dashami) and each ritual: anjali mantra, Sandhi Puja, Kumari Puja, Kola Bou, sindoor khela, dhunuchi |
| `/durga-puja/at-home/`, `/durga-puja/samagri-list/` | How to do the puja at home (HowTo), the items checklist |
| `/navratri/…` | Navratri: Navadurga, ghatasthapana, fasting, kanya pujan, Dussehra, garba |
| `/durga-puja/glossary/` | 45+ terms (DefinedTermSet) |
| `/guide/` | Kolkata hub: areas, most-visited pandals, trails, FAQ |
| `/guide/dates/` | "When is Durga Puja 2026?" Mahalaya to Dashami, with crowd levels |
| `/guide/areas/<zone>/`, `/guide/pandals/<id>/`, `/guide/food/<id>/`, `/guide/trails/<id>/`, `/guide/parking/` | Every area, pandal (107), eatery (175), trail, parking |
| `/sitemap.xml` (with images), `/robots.txt` | Every page; all crawlers, AI included, allowed |
| `/llms.txt`, `/llms-full.txt`, `…/index.md` | The [llms.txt](https://llmstxt.org) index, the whole guide as text, and a Markdown copy of every article |
| `/404.html` | Missing pages point back to the hubs |

## Adding or editing an article

Write Markdown with a short TOML header in `content/knowledge/` (format and writing rules: `content/knowledge/README.md`),
push, and the deploy publishes it.

- **Broken links stop the deploy.** Every link to another page must point at a page the build creates, so a
  broken link fails the build. `python scripts/build_seo.py --out /tmp/x --preview` only warns, for drafting.
- **Changed pages are announced to IndexNow.** After each deploy, every page whose content changed is sent to
  IndexNow (Bing, which feeds ChatGPT search and Copilot, plus Yandex and others). It works by comparing the
  page fingerprints in `seo-manifest.json` with the live site; the key file is `app/<indexnow_key>.txt`.

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

The site's address is **https://pujoparikramaguide.in/** (`site.json`). Every canonical URL, the sitemap and
`llms.txt` use it, and the old github.io address redirects there.

1. **Google Search Console** (<https://search.google.com/search-console>):
   - Choose **Add property → Domain** and enter `pujoparikramaguide.in`. A Domain property covers `https`, `http` and `www` in one go.
   - Google shows a **TXT record** (`google-site-verification=…`). Add it in your domain registrar's DNS settings
     as a TXT record on the root (`@`), then click **Verify**. DNS can take a few minutes to an hour.
   - **Sitemaps** → submit `https://pujoparikramaguide.in/sitemap.xml`.
   - Optional: **URL inspection** → `https://pujoparikramaguide.in/guide/` → **Request indexing**, to speed up the first crawl.
   - If you can't edit DNS, use a **URL prefix** property instead, with **HTML tag** verification.
     Put the tag's `content` value in `site.json` as `"google_site_verification"`. The deploy adds it to every page.
2. **Bing Webmaster Tools** (<https://www.bing.com/webmasters>): **Import from Google Search Console**, one click.
   Bing's index feeds ChatGPT search and Microsoft Copilot.

## Limits to know

- **Crawler files sit at the root.** On the domain, `robots.txt`, `sitemap.xml` and `llms.txt` are at
  `https://pujoparikramaguide.in/…`, where crawlers look for them. If the domain ever changes, run
  `python scripts/site.py set https://new-domain/` and every canonical URL follows.
- **Pages are English.** Bengali names appear alongside, and the app itself is in English, Bengali and Hindi.
- **Indexing takes days to weeks.** Pandal pages have the best chance of ranking for long-tail searches like
  "<pandal> best time to visit" or "<pandal> nearest metro".
