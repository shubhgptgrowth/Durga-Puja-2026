# Google AdSense

Ads appear on the **guide pages** only: articles, recipes, Kolkata pandal and eatery pages, and the card maker. They never
appear in the app (`/`, where people plan routes and check in), or on About, Contact, Terms, Search or the 404 page.
Everything is switched by one value in `site.json`:

```json
"adsense_client": "ca-pub-1234567890123456"
```

Empty means no ads anywhere; this is the default. Once it's set, the next deploy:

- adds the AdSense tag to every guide page's `<head>`. Ad placement is chosen by **Auto ads** in AdSense, so there are no
  hand-placed slots to maintain.
- adds the `google-adsense-account` verification tag to the home page. The tag carries no ads.
- publishes `ads.txt` at the site root: `google.com, pub-…, DIRECT, f08c47fec0942fa0`.

## Getting approved (one time)

1. **Sign up** at <https://adsense.google.com> with the site `pujoparikramaguide.in`.
2. **Copy your publisher ID** (`ca-pub-…`) into `site.json` → `adsense_client`, and push. Or ask Claude to do it.
3. **Verify the site.** In AdSense → Sites, choose **Verify** with the *AdSense code snippet* or *meta tag* method. Both are
   already on the home page after the deploy.
4. **Request review.** Google checks the site, which can take a few days to a few weeks.
5. **Set up consent before ads go live.** In AdSense → **Privacy & messaging**, create a **European regulations** (GDPR) message,
   which uses Google's certified consent banner. It's needed for visitors from the EEA, UK and Switzerland. The privacy policy
   already explains advertising cookies and how to opt out (`/privacy.html#ads`).
6. **Turn on Auto ads** in AdSense → Ads → By site. A moderate ad load keeps pages readable. Excluding the card maker is optional.

## What reviewers look for, and where the site stands

| Requirement | Here |
|---|---|
| Substantial, original content | 60+ in-depth articles on rituals, mantras, history, recipes, Navratri, festivals and travel, plus 300 Kolkata pages |
| Clear navigation | Section menu on every page, hubs, breadcrumbs, search, "Read next" |
| About, Contact, Privacy, Terms | `/about/`, `/contact/`, `/privacy.html`, `/terms/`, linked in every footer |
| Privacy policy covers ads | "Advertising and cookies" section, with links to opt out |
| No broken pages | The build fails on broken links; missing pages get a helpful 404 |
| Mobile-friendly, fast | Plain HTML and CSS, no frameworks, about 20 KB per page before images |

**Worth doing before you apply:**

- **Read a sample of articles yourself.** They were drafted with AI help and checked against their sources. The About page says
  so. Any correction or personal detail you add, such as your family's puja or a photo you took, makes the site more trustworthy.
- **Put a real name or team on the About page.** Google rewards visible, accountable authors (E-E-A-T), so a short line about who
  runs the guide helps.

## Rules to keep

- Never click your own ads, and never ask others to.
- Don't put ads inside the app, next to the check-in or upload buttons, or on pages with little content.
- Keep content original. Don't copy text from other sites.
