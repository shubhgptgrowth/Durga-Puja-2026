# Restaurant offers and menu photos

## Pujo offers

1. An owner or manager opens their eatery in the app → **Post a pujo offer** (bottom of the page): the offer,
   optional details, valid from/till (up to 60 days ahead), their name and a 10-digit mobile number, and a tick
   for "I own or manage this place". Five per person per day.
2. It is stored as **pending** (`public.food_offers`) and nobody sees it yet.
3. The team calls the number back. Find it in the Supabase dashboard → Table editor → schema `analytics` →
   `offers_pending`. The number is never in a public view, the app, a log or the job summary.
4. Approve: Actions → **offers** → Run workflow → action `approve`, offer id (from the daily list or the
   dashboard). `reject` hides it; `pending` puts it back. Or in the SQL editor:
   `select public.review_offer('<id>', 'approved');`
5. Approved offers show on the eatery page (🏷️ card) and as a "Pujo offer" tag on its tile in Explore → Food,
   until the "till" date passes. The app reads them from `public.offers_feed` (no contact fields).

The **offers** workflow also runs daily at 09:45 IST and lists what's waiting.

## Featured (paid) offers

Phase 0 of [BUSINESS_ROADMAP.md](BUSINESS_ROADMAP.md). The rate card, pitch and call list are in [../marketing/FEATURED_OFFERS.md](../marketing/FEATURED_OFFERS.md).

* **The owner asks.** The offer form has a **Feature it** tick, with the price from `featured.priceInr` in `app/config.js`. It is stored as `wants_featured`, and those offers sit at the top of `analytics.offers_pending`.
  * If `featured.upiId` is set, the owner gets a *Pay by UPI* button after sending. The amount is filled in, and the note carries the offer's short id.
  * Without a UPI id, payment is taken on the call.
* **The team switches it on after payment.**
  * In the SQL editor: `select public.feature_offer('<id>', '<last day>', '<payment note>')`. The note is visible only in `analytics.offers_featured`.
  * Or the **offers** workflow, action `feature` with *featured until*. Never put payment details in the workflow: the repo is public.
  * Featuring also approves the offer, and never runs past the offer's own end date. `feature_offer('<id>', null)` or action `unfeature` turns it off.
* **What diners see.**
  * `offers_feed.featured` is true.
  * The card and the food-list chip are labelled **Sponsored** (স্পনসরড / प्रायोजित).
  * The eatery is listed first in Explore → Food and in "Food nearby" on pandal pages, still labelled.
  * Nothing else moves: crowd estimates, routes and pandal order never depend on payment.
* **Deploy order.** Run **supabase-setup** (it applies `*_featured_offers.sql`) when this ships. Until then the app still submits offers, without the featured flag.

## Menu photos

Anyone can add a menu or price-board photo from the eatery page (**Menu → Add menu photo**). They are normal
uploads to the `moments` bucket tagged `menu` (`photos.tag`), shown under Menu on that eatery and kept out of
the Moments feed and the photo counts. Reporting and hiding work as for any moment (three reports hide it).
