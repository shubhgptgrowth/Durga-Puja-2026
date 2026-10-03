# Hosting on a custom domain

**Today:** the app is on GitHub Pages at `https://shubhgptgrowth.github.io/Durga-Puja-2026/`.
**Goal:** a short address (for example `pujoparikrama.in`) that's easy to say on posters, and enough bandwidth for lakhs of visitors.

## Recommendation: GitHub Pages + your domain, with Cloudflare in front

| | GitHub Pages + domain, Cloudflare DNS/CDN (**recommended**) | Cloudflare Pages |
|---|---|---|
| Cost | Domain only (≈ ₹500–900/year for `.in`). GitHub and Cloudflare free plans | Same |
| Bandwidth | Cloudflare serves cached files from its edge, so GitHub's ~100 GB/month soft limit stops mattering | Unlimited |
| Old links and printed QR codes | **GitHub redirects the old github.io address to the domain automatically**, keeping path, `?src=` and `#p=` | Needs a redirect shim on the old site |
| Big files | No per-file limit that matters (the vector map file is tens of MB) | 25 MiB per-file limit: the map file would need R2 |
| Deploy changes | None. The existing `deploy` workflow keeps working | A new deploy pipeline and API token |

## What's already wired

* **`site.json`** holds the public address. `python scripts/site.py set https://<domain>/` updates it, together with the link-preview tags in `app/index.html`. A test keeps them in sync.
* The **content kit, story cards, QR posters and flyer** all print and link whatever `site.json` says. After the switch, the next morning's kit (or any deploy) has the new address.
* The **`deploy` workflow**:
  * sets the GitHub Pages custom domain from `site.json` (the `domain` job);
  * checks the live site at the new address;
  * checks that the old github.io address redirects to it.

## Steps

1. **Buy the domain.** Any registrar works (GoDaddy, Hostinger, Namecheap, BigRock…). Suggestions, in order: `pujoparikrama.in`, `pujoparikrama.com`, `pujo.guide`. Skip the registrar's paid add-ons (email, "SSL", hosting).
2. **Put the domain on Cloudflare** (free plan):
   * Add a site at dash.cloudflare.com and pick the Free plan.
   * At your registrar, replace the nameservers with the two Cloudflare gives you. This takes from minutes up to a few hours.
3. **DNS records in Cloudflare.** Set both to **DNS only (grey cloud)** for now:

   | Type | Name | Target |
   |---|---|---|
   | CNAME | `@` | `shubhgptgrowth.github.io` |
   | CNAME | `www` | `shubhgptgrowth.github.io` |

4. **Switch the app over.** Tell Claude the domain, or run `python scripts/site.py set https://<domain>/` and push. The deploy then sets the custom domain on GitHub Pages.
   * If the `domain` job warns that it couldn't, set it by hand: repo **Settings → Pages → Custom domain** = `<domain>` → Save.
   * Optional: add a fine-grained token with the "Pages: write" permission as the secret `PAGES_ADMIN_TOKEN`, so the job can do it itself next time.
5. **HTTPS.** GitHub issues a certificate within about an hour. Then tick **Settings → Pages → Enforce HTTPS**.
6. **Turn on the Cloudflare CDN:**
   * Switch both DNS records to **Proxied (orange cloud)**.
   * Set **SSL/TLS** mode to **Full (strict)**.
   * Under **Caching → Cache Rules**, add a rule: URI path ends with `.pmtiles` or starts with `/vendor/` or `/icons/` → *Eligible for cache*, Edge TTL 1 day.
   * Leave HTML and `data/guide.json` uncached (they change with every deploy).
7. **Check:**
   * The deploy's `verify` job is green.
   * The old `shubhgptgrowth.github.io/Durga-Puja-2026/?src=qr_test#p=sreebhumi` lands on the new domain, on Sreebhumi.
   * Update the Instagram bio link and WhatsApp Channel link to the new domain (keep `?src=ig_bio` / `?src=wa_channel`).

**Order matters.** Don't set the custom domain (step 4) before the DNS records (step 3) exist. GitHub would start redirecting the old address to a domain that doesn't resolve yet.

## Rollback

`python scripts/site.py set https://shubhgptgrowth.github.io/Durga-Puja-2026/` and push. The `domain` job clears the custom domain, and GitHub serves the github.io address again.
