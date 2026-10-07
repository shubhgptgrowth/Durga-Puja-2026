# Featured pujo offers: rate card, pitch and target list (Phase 0)

> Phase 0 of [../product/BUSINESS_ROADMAP.md](../product/BUSINESS_ROADMAP.md): the first money, before Shashthi.
> How the feature works in the app and the backend: [../product/OFFERS.md](../product/OFFERS.md).
> **On hold (7 Oct).** At about 170 devices, no eatery will pay for reach yet. The paid option is switched off in the app
> (`featured.priceInr: 0`). Featuring still works from the team side, so a partner eatery can be featured for free in
> exchange for a QR standee at its counter, if the owner approves that plan. Switch pricing back on once weekly
> visitors justify it (about 10,000 a week).

## What the eatery gets

| | Free offer | **Featured offer** |
|---|---|---|
| Offer card on their page in the app | ✓ | ✓, highlighted, labelled **Sponsored** |
| "Pujo offer" tag in the food list | ✓ | ★ "Sponsored · Pujo offer" |
| **Listed first** in the food list and in "Food nearby" on every nearby pandal's page | – | ✓, labelled Sponsored |
| Post-puja report: how many times their page was opened and how many people tapped Directions | – | ✓ (from `analytics.places`) |

**The honesty rule, said out loud on every call:** featuring moves an eatery up in *food* lists and labels it
Sponsored. It never changes crowd times, routes or pandal order, and the app never says "recommended" about a paid listing.

## Prices (owner can change these)

| Package | Price | Notes |
|---|---|---|
| **Featured, the puja days** (start date to Dashami, 21 Oct) | **₹1,999 until 12 Oct**, then ₹2,999 | The early price gives a reason to decide this week. Change `featured.priceInr` in `app/config.js` on 13 Oct |
| **Featured + Instagram** | ₹4,999 | Featured, plus one story on @pujoparikrama.guide and a mention in a daily food card, at our choice of day |
| First 5 eateries that say yes | Featured at ₹1,499 | Use it to close the first ones fast and get logos for "already featured" |

Prices cover the 5 puja days. An offer may start earlier (from Mahalaya) at the same price.

## How it runs, step by step

1. **The eatery posts its offer** in the app: open the eatery → *Post a pujo offer* → tick **Feature it**. Or the team does it for them on the call, in the eatery's name.
2. **The team calls back.** Numbers are in the dashboard, `analytics.offers_pending`; the ones who asked to be featured are at the top. Confirm the offer and the dates, and take payment by UPI.
3. **Payment.**
   * **With a UPI id in `app/config.js`** (`featured.upiId`): the owner gets a *Pay by UPI* button right after sending. The note carries the offer's short id.
   * **Without one:** send your UPI QR or id on WhatsApp.
   * Never write payment details in a GitHub workflow or issue: the repo is public.
4. **Record the payment and switch it on:**
   * In the Supabase SQL editor: `select public.feature_offer('<offer id>', '2026-10-21', 'Rs 1999, UPI ref …');`
   * Or Actions → **offers** → action `feature`, offer id, featured until `2026-10-21`. Then add the payment note in the dashboard.
5. **It is live on the next app open.** Check it: Explore → Food shows the eatery first with "Sponsored".
6. **After Bijoya:** send each featured eatery its numbers (page opens, Directions taps, check-ins "I ate here"). That report is what sells next year.

To switch one off: action `unfeature`, or `select public.feature_offer('<id>', null);`.

## The pitch

**On the phone or at the counter (Bengali):**

> নমস্কার, আমি পুজো পরিক্রমা থেকে বলছি। কলকাতার ঠাকুর দেখার একটা ফ্রি অ্যাপ। কোন প্যান্ডেলে কখন ভিড় কম,
> আর প্যান্ডেলের কাছে কোথায় খাবেন, সেটা দেখায়। আপনার দোকান আমাদের অ্যাপে আছে, {pandal}-এর পাশে।
> পুজোর পাঁচ দিন আপনার একটা অফার, ধরুন "থালির সঙ্গে মিষ্টি দই ফ্রি", আমরা সবার আগে দেখাব, পাশের সব প্যান্ডেলের পাতায়।
> "স্পনসরড" লেখা থাকবে। ১২ তারিখ পর্যন্ত খরচ ১,৯৯৯ টাকা। পুজোর পরে আপনাকে জানিয়ে দেব কতজন আপনার পাতা খুলেছেন,
> কতজন রাস্তা দেখেছেন। অফারটা কী রাখবেন বলুন, আমি এখনই তুলে দিচ্ছি।

**English (for chains and managers):**

> Hi, I'm calling from Pujo Parikrama, a free Kolkata pandal-hopping guide that shows when each pandal is quiet and
> where to eat nearby. {Eatery} is already in it, next to {pandal}. For the five puja days we can feature one pujo
> offer of yours at the top of the food list on every nearby pandal's page, labelled Sponsored, for ₹1,999 if you
> decide by the 12th. After the pujas we'll send you how many people opened your page and asked for directions.
> What offer would you like to run?

**Objections:**

* **"How many people use it?"**
  * Give the real number from the latest reach report, and the plan: the push from Mahalaya, the press, the creators.
  * Never inflate it.
  * If the number is small, lead with the price and the post-puja report: "you'll see exactly what it did".
* **"We're full anyway during pujo."**
  * The offer can push the slow hours instead: "10% off before 6 pm".
  * Or a new item: the bhog thali, the takeaway box.
* **"Swiggy/Zomato already list us."**
  * This is different. It reaches people standing at the pandal next door, at the moment they decide where to eat. Not a delivery app.
* **"Can you put us on top without the Sponsored label?"** No, never.

## Target list: who to call first

These are the eateries within walking distance of the 20 most popular pandals. They're ordered by how many of
those pandals list them in "Food nearby", weighted by the pandal's popularity, and then by walking time.
Groups of street stalls and food courts are left out, since there's no single owner to call.

**Tier 1: call by 9 Oct**

| # | Eatery | Area | Type | Next to (walk) |
|---|---|---|---|---|
| 1 | Nobin Chandra Das & Sons (Bagbazar) | Kumartuli, Bagbazar & Hatibagan | sweets | Kumartuli Park, Bagbazar (3 min) |
| 2 | Putiram | College Street & Sealdah | sweets | College Square, Mohammad Ali Park (4 min) |
| 3 | Mirch Masala | Gariahat & Ballygunge | restaurant | Ekdalia Evergreen, Singhi Park (6 min) |
| 4 | Ammini | Lake Market & Kalighat | restaurant | Tridhara, Maddox Square (7 min) |
| 5 | Allen's Kitchen | Kumartuli, Bagbazar & Hatibagan | cabin | Sovabazar Rajbari, Ahiritola (10 min) |
| 6 | Kowloon | Behala & New Alipore | restaurant | Suruchi Sangha (1 min) |
| 7 | Swadhin Bharat Hindu Hotel | College Street & Sealdah | restaurant | College Square (2 min) |
| 8 | Paramount | College Street & Sealdah | drinks | College Square (2 min) |
| 9 | Favourite Cabin | College Street & Sealdah | cabin | College Square (4 min) |
| 10 | Benfish | Kumartuli, Bagbazar & Hatibagan | restaurant | Tala Prattoy (5 min) |
| 11 | MOMO HUY | Kumartuli, Bagbazar & Hatibagan | restaurant | Tala Prattoy (5 min) |
| 12 | The Fat Monk | Salt Lake | street | FD Block (5 min) |
| 13 | Apanjan | Lake Market & Kalighat | street | Badamtala Ashar Sangha (5 min) |
| 14 | Ikura - Flavours of Pan Asia | Lake Market & Kalighat | restaurant | Chetla Agrani (6 min) |
| 15 | Bhojohori Manna 6 | Gariahat & Ballygunge | restaurant | Singhi Park (6 min) |

**Tier 2: call 10–12 Oct**

| # | Eatery | Area | Type | Next to (walk) |
|---|---|---|---|---|
| 16 | Vivekananda Park Phuchka | Lake Market & Kalighat | street | Singhi Park, Tridhara (9 min) |
| 17 | 6 Ballygunge Place | Salt Lake | restaurant | FD Block (7 min) |
| 18 | Shree Ram Dhaba | College Street & Sealdah | restaurant | Mohammad Ali Park (7 min) |
| 19 | Ubuntu Eat | Behala & New Alipore | drinks | Suruchi Sangha (7 min) |
| 20 | Mitra Cafe (Sovabazar) | Kumartuli, Bagbazar & Hatibagan | cabin | Sovabazar Rajbari (7 min) |
| 21 | Momo I Am | Salt Lake | restaurant | FD Block (8 min) |
| 22 | Indian Coffee House | College Street & Sealdah | cabin | Mohammad Ali Park (8 min) |
| 23 | Sen Sweets | College Street & Sealdah | sweets | Santosh Mitra Square (8 min) |
| 24 | Potboiler Coffee House | Lake Market & Kalighat | drinks | Tridhara (8 min) |
| 25 | Bojangles | Bhowanipore & Elgin | restaurant | Maddox Square (8 min) |
| 26 | Tasty Corner | Gariahat & Ballygunge | restaurant | Ekdalia Evergreen (9 min) |
| 27 | Mio Amore | Lake Town & Dum Dum | sweets | Sreebhumi (9 min) |
| 28 | Sharma Snacks | Lake Town & Dum Dum | street | Sreebhumi (9 min) |
| 29 | New Madras Tiffin | Kumartuli, Bagbazar & Hatibagan | restaurant | Sovabazar Rajbari (9 min) |
| 30 | 7th Mandeville Multi Cuisine Restro | Gariahat & Ballygunge | restaurant | Ekdalia Evergreen (10 min) |
| 31 | Dilkhusha Cabin | College Street & Sealdah | cabin | Mohammad Ali Park (10 min) |
| 32 | Sienna Store & Cafe | Gariahat & Ballygunge | drinks | Singhi Park (10 min) |
| 33 | Rose | Lake Town & Dum Dum | restaurant | Sreebhumi (10 min) |
| 34 | Royal Biryani | Kumartuli, Bagbazar & Hatibagan | street | Tala Prattoy (11 min) |
| 35 | Prema Vilas | Lake Market & Kalighat | restaurant | Badamtala Ashar Sangha (12 min) |

Log every call in [TRACKER.md](TRACKER.md) §3 (Eateries): asked, yes/no, offer, paid, featured until. Phone
numbers stay in the dashboard or the caller's phone, never in this public repo. Chains (Bhojohori Manna, Mio Amore,
Mirch Masala) decide centrally: ask for the marketing manager and offer one price for several branches.
