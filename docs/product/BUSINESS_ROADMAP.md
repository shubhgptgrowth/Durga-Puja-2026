# Beyond this pujo: reaching more people, and making money (draft for owner approval, 7 Oct 2026)

> Companion to [../marketing/STRATEGY.md](../marketing/STRATEGY.md), which covers the 1-lakh push up to Bijoya.
> This file covers what comes after: how the audience grows past one festival, and how it pays for itself.

## The honest starting point

* **The audience is seasonal.** Durga Puja traffic is about 10 days a year, peaking on 5 nights. A business
  built only on those nights has about 10 days a year to earn.
* **What we really own is three things:**
  1. A **festival crowd-and-route engine**: places, quiet-hour estimates from a crowd model, live check-ins, walking routes by metro and auto, food nearby.
  2. **Real footfall data**: verified check-ins by pandal and hour. Nobody else has it except the police.
  3. **A Bengali-first brand** for festival culture, with ~440 crawlable pages that keep earning search traffic year after year.
* **What not to do:** don't sell personal data, don't let money change the crowd advice, and don't add features nobody uses. The contacts list stays opt-in and never leaves the team.

## Part 1: How we reach many more people

### 1. More festivals, same engine (Bengal's festival calendar)

The app already knows Kolkata's streets, metro and food. Every big Bengal festival has the same problem: where to go, when it's quiet, how to get there.

| When | Festival | What the app does | Effort |
|---|---|---|---|
| Late Oct 2026 (Sharad Purnima) | Kojagari Lakshmi Puja | Home-puja guide, bhog recipes (content exists) | Content only |
| Nov 2026 (Kartik Amavasya) | **Kali Puja and Diwali** | A Kali Puja pandal map (Barasat, Naihati and big Kolkata pujas), firecracker-free zones, Bhai Phonta | Data plus a re-skin |
| Nov 2026, about 9 days after Kali Puja | **Jagaddhatri Puja, Chandannagar** | The same route engine for Chandannagar's lighting pujas, plus a train guide from Howrah | New area data |
| 25 Dec 2026 | Park Street Christmas | Crowd timing, food, metro | Small |
| Late Jan to Feb 2027 | **Kolkata Book Fair** and **Saraswati Puja** | Stall map, college-crowd routes | Medium |
| Apr to Jul 2027 | Poila Baisakh, Rath Yatra | Content and short guides | Small |

**Why it matters:** it turns 10 days into about 60 days of use, keeps the WhatsApp Channel and Instagram alive all year, and gives sponsors more than one moment to buy.

### 2. Durga Puja beyond Kolkata (the probashi market)

UNESCO heritage status made Durga Puja global. Large Bengali communities run hundreds of pujas outside Bengal:
* **Delhi:** CR Park, plus about 800 pujas across the NCR.
* **Mumbai and Pune.**
* **Bengaluru:** pujas run by the Bengali associations.
* **Guwahati and Siliguri.**
* **Abroad:** the US, UK, Dubai and Singapore, mostly on weekends.

The same "pandals near me, when it's quiet, what's the theme" product works for each of them. Probashi Bengalis are also the people most likely to forward Bengali-first content.

**2027 target:** Kolkata plus Delhi-NCR and Bengaluru, then a directory of pujas abroad with livestream links.

### 3. Other crowd festivals in India (the platform play, 2027+)

The engine isn't Bengali-specific. Festivals with the same queue problem include:
* **Ganesh Chaturthi in Mumbai** (Lalbaugcha Raja's darshan queue runs 10–20 hours).
* **Navratri garba in Ahmedabad and Vadodara.**
* **Mysuru Dasara.**
* **Thrissur Pooram.**
* **The Jagannath Rath Yatra in Puri.**

Do one pilot (Mumbai Ganesh, Sep 2027) before committing to more.

### 4. Owned audience, so each season starts warm

* **WhatsApp Channel subscribers and opted-in contacts:** these are the list we can reach without paying anyone. Target 25,000 Channel followers by Bijoya.
* **The PWA installed on home screens:** an install prompt after a saved plan (G6 in the strategy).
* **Search compounds:** the domain, its backlinks from press and the evergreen guides (rituals, recipes, dates) grow every year. Start the 2027 season in **July 2027**, not October.
* **Puja committees as distribution partners:** their QR posters, plus a "claim your pandal" page (see M6) so committees update their own theme and timings.

## Part 2: How we make money

The rules: every paid placement is labelled **Sponsored**. Paid placements never change quiet-hour estimates, routes or rankings. Aggregate data only; no personal data is ever sold.

### Revenue lines, ranked by how soon they can pay

| # | Revenue line | Who pays | What they get | Rough size, year 1 | Readiness |
|---|---|---|---|---|---|
| R1 | **Featured eatery offers** | Restaurants and sweet shops near big pandals | A "Featured pujo offer" card and top placement in "Food nearby", for the 5 days | ₹999–₹4,999 per eatery × 20–60 eateries ≈ **₹0.5–2L** | The offers flow exists. Needs pricing, a UPI payment link and a "Sponsored" label |
| R2 | **Title sponsor** "Pujo Parikrama, presented by X" | Brands that spend big in pujo season: sweets, ethnic wear, telecom, paints, two-wheelers, beverages, banks | Name on the app, the kit cards and the story cards, plus a sponsored trail ("X Mishti Trail") | **₹1–5L** for 2026 if reach crosses 1 lakh. Much more in 2027 with a media kit in June | Needs a media kit with real numbers (the reach report has them from today) and an invoice |
| R3 | **Affiliate links** | Hotels (for tourists and NRIs), cabs and rides, ethnic wear, puja samagri | Commission per booking or sale | ₹10–50k | Small: links in the visitor, what-to-wear and samagri articles |
| R4 | **Display ads (AdSense)** on guide pages only | Google | ~₹20–60 per 1,000 page views in India | ₹10–30k this season, growing with search | Built. Apply now (approval takes days to weeks), then set `adsense_client` |
| R5 | **Footfall reports for committees** | Puja committees, who use them to sell their own sponsors and plan crowds | A post-puja report: check-ins by hour and day, versus other pandals in the area, share of visitors from metro | ₹5–25k per committee × 10–30 committees ≈ **₹1–5L** (2027) | Needs the check-in data from this season and a report generator (M5) |
| R6 | **Guided walks and tours marketplace** | Walk operators: heritage walks, bonedi bari tours, photography walks | Bookings through the app, 10–20 % commission | ₹0.5–2L | Partner deals, plus a booking link (M8) |
| R7 | **Licensing the engine** | Tourism boards, other cities' festival organisers, event organisers (Book Fair) | A white-label crowd-and-route guide | Big but slow; 2027–28 | After 2–3 more festivals prove it (M7) |

**Realistic year 1 (Oct 2026 – Sep 2027): about ₹3–12 lakh.** Most of it comes from R1, R2 and R5. The bigger
prize is pujo 2027: brands decide their pujo budgets in June to August, so a media kit built on 2026 numbers
must be in their inboxes by June 2027.

### What NOT to sell

* **Paid "quietest pandal" placement or paid ranking.** It would destroy the one promise the brand rests on.
* **Contact lists or personal data,** to anyone.
* **A paid app for users.** Pujo-goers won't pay, and it would kill sharing. An optional ₹49 offline map pack can be tested in 2027 at most.

## Part 3: The product roadmap that supports this

| # | Item | For | When | Size |
|---|---|---|---|---|
| M1 | **Sponsored label plus paid featured offers:** a price per eatery, a UPI or Razorpay payment link, approve after payment, and a "Sponsored" tag on the card and tile | R1 | **Before Saptami (by 15 Oct)** | Small |
| M2 | **Sponsor slots:** a "presented by" band on Home, a sponsor frame on story cards and kit cards, a sponsored trail. Each slot can be switched off from one config file | R2 | By 14 Oct if a sponsor signs; otherwise 2027 | Small |
| M3 | **Affiliate links** in the visitor, what-to-wear and samagri articles, tracked with their own link codes | R3 | Oct 2026 | Small |
| M4 | **AdSense on:** apply now, set `adsense_client` once approved | R4 | When approved | Tiny |
| M5 | **Post-puja footfall reports:** one page per pandal from verified check-ins plus the crowd model, aggregates only, as a PDF a committee can show sponsors | R5, press | 22 Oct – 15 Nov 2026 | Medium |
| M6 | **Committee portal "Claim your pandal":** verify by phone, update the theme, timings and photos, see the live check-in count. A paid tier adds the footfall report | R5, data quality | Pilot with 10 committees, Jan–Jun 2027 | Large |
| M7 | **Multi-festival, multi-city engine:** generalise "pandal" into "venue" and "puja days" into "event days". One data folder per event (Kali Puja, Chandannagar, Book Fair, CR Park, Mumbai Ganesh) | Reach, R7 | Kali Puja (Nov 2026) is the first test; generalise properly by Apr 2027 | Large |
| M8 | **Tours and walks booking:** partner listings on trail pages, booking by link or WhatsApp, commission tracked by link code | R6 | Pilot Dec 2026 – Feb 2027 | Medium |
| M9 | **Media kit page:** live reach numbers (devices, cities, top sources), audience mix and case studies, generated from the reach report | R2, R5 | First version 22 Oct 2026; 2027 edition by 1 Jun 2027 | Small |

## Part 4: Timeline

| Window | Focus | Money moves |
|---|---|---|
| **7–21 Oct 2026** (now → Dashami) | The 1-lakh push (STRATEGY.md). Nothing here may slow it down | M1 featured offers (sell to the 20 eateries near the top pandals); one title-sponsor pitch after the Mahalaya numbers; apply for AdSense; M3 affiliate links |
| **22 Oct – 30 Nov 2026** | Bijoya recap press story. Kojagari, Kali Puja and Diwali, Chandannagar Jagaddhatri on the same engine | M5 footfall reports to all committees (free this year, as the hook for 2027); M9 media kit v1 |
| **Dec 2026 – Mar 2027** | Christmas, Book Fair, Saraswati Puja. Grow the Channel and the contact list | M6 committee portal pilot; M8 walks pilot; letters of intent with 10 committees and 2–3 brands for 2027 |
| **Apr – Jun 2027** | M7 generalised engine; Delhi-NCR and Bengaluru data; a 2027 brand refresh | **Sponsor sales season:** the media kit goes to brands by 1 June |
| **Jul – Oct 2027** | Pujo 2027 starts in July (search, Channel, committees), with a Mumbai Ganesh pilot in September | Title sponsor, featured eateries, committee tier, affiliates, ads |

## Part 4b: Phasing under competition (added 7 Oct)

**Who else is in the race (2025–26):**
* **Kolkata Police's Puja Bandhu:** live crowd counts and nearest metro. Official, free, police distribution.
* **West Bengal Tourism's Sharadotsav app:** maps and zone-wise pujas.
* **Utsav:** 500+ committees and bonedi baris, online dakshina, follow-a-committee. The closest to a committee business.
* **Swiggy ShresthoPujo:** pandal voting inside an app with tens of millions of users, with cash prizes for the winning pandals.
* **Brand campaign apps** such as Titan's pandal locator and Sunrise Spices' AI pandal hopping.

**What this means:**
1. **We won't win a download race this season.** Swiggy and the police have distribution we can't match by 17 Oct.
2. **Most of these aren't businesses.** The police and tourism apps are public services. Swiggy, Titan and Sunrise are one-season marketing campaigns. Brands paid to *build* them, which makes those brands **customers**, not only competitors: next year it's cheaper for them to sponsor or white-label ours than to build again.
3. **Where we're different, and where to dig in:**
   * We help people **plan ahead** (quiet hours by day, a walking route, food on the way), not only see live counts.
   * We're a **web link, not an app install**, so we travel on WhatsApp in one tap.
   * We're **Bengali-first**.
   * We're building a **search moat** (440 pages).
   * We have **verified footfall data**.
   * We **ship faster** than any of them.
4. **Play where they aren't:** Kali Puja, Barasat, Naihati, Chandannagar Jagaddhatri, probashi pujas in Delhi and Bengaluru, and the evergreen guides. Puja Bandhu, ShresthoPujo and the brand apps are Durga-Puja-in-Kolkata only.

### The phases

| Phase | Window | Goal | Money | Exit test |
|---|---|---|---|---|
| **0. Grab what's reachable** | Now → 16 Oct | Reach (STRATEGY.md), plus proof that someone will pay | **Featured eatery offers** (M1), sold by phone or in person to the ~40 eateries next to the top-20 pandals. **Micro-sponsors** (local sweet shops, cafés, regional brands) at ₹10–50k or barter. Big brands' pujo budgets were locked in July–August, so don't wait on them | ≥10 paying eateries, or 1 micro-sponsor |
| **1. Bank the data** | 17–21 Oct (the five days) | Most verified check-ins and crowd reports, and the most WhatsApp Channel joins and opted-in contacts. This data is what we sell later | Only what Phase 0 sold. **No new ad units on puja nights:** trust and speed matter more | ≥5,000 check-ins, ≥10,000 Channel followers |
| **2. Turn the season into assets** | 22 Oct – 30 Nov | Footfall reports (M5) to every committee, free. A recap press story with real numbers. Media kit v1 (M9). **Kali Puja and Chandannagar run monetised from day one**, where the big apps don't play | Eatery offers and a sponsor for Kali Puja and Chandannagar; AdSense on guide pages | ≥30 committees receive their report; ≥1 paid deal for Kali Puja or Chandannagar |
| **3. B2B before B2C** | Dec 2026 – Mar 2027 | The **committee portal** (M6): committees claim their pandal, post their theme early and see their footfall, before Utsav locks them in. An **embeddable quiet-hours widget** for news sites: free with credit, giving backlinks and reach; a paid API later. A **white-label pitch** to the brands that built their own 2026 apps | Committee tier (₹5–25k), walks commissions | ≥50 committees claimed; ≥2 brand meetings booked |
| **4. Sell 2027 before anyone else** | Apr – Aug 2027 | The multi-festival, multi-city engine (M7); Delhi and Bengaluru data | **Title sponsor and brand partners signed by July**, while pujo budgets are being set | 1 title sponsor signed |
| **5. Fully monetised season** | Sep – Oct 2027 | Pujo 2027 in three cities, plus a Mumbai Ganesh pilot | Sponsor, featured eateries, committee tier, affiliates, ads, widget API | Revenue covers the year's costs |

**Kill or pivot test (25 Oct 2026):** if the season ends under 25,000 devices *and* under 2,000 check-ins, the
consumer brand isn't strong enough on its own. Then the bet becomes the B2B layer (committee portal, footfall
data, white-label engine for brands and tourism), with the consumer site kept as its showcase.

## Part 5: Decisions needed from the owner

0. **Approve the phasing in Part 4b.** Phase 0 starts today: someone has to call or visit eateries this week.
1. **Is this a business or a passion project?** A business needs a legal entity, a bank account and GST, so sponsors can be invoiced. It can start as a proprietorship.
2. **Can we start selling now?** That means M1 (paid featured offers) and one title-sponsor pitch this season, with the "Sponsored" label and the rule that paid placements never change crowd advice.
3. **Do we apply for AdSense now?** Ads would show on guide pages only, never in the app.
4. **Which second festival first?** I recommend Kali Puja and Chandannagar Jagaddhatri in Nov 2026: same city, same engine, three weeks later.
5. **Is the 2027 ambition Kolkata-only, or Kolkata plus two cities?** That decides whether M7 starts in December or April.
