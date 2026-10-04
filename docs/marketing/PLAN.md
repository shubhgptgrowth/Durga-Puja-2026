# Marketing playbook: Instagram + WhatsApp, 3–22 October 2026

> **Marketing track.** This is the plan. Progress, owners and partners go in [TRACKER.md](TRACKER.md). App changes are requested from the product track: [../product/ROADMAP.md](../product/ROADMAP.md).

**Goal:** every pandal hopper in Kolkata opens Pujo Parikrama at least once during the pujas.

We can't count people, so we count **devices**: phones that open the app. The count is anonymous and per day. The goal ladder:

| Level | Devices by Dashami (21 Oct) | What it takes |
|---|---|---|
| Floor | 25,000 | Instagram and WhatsApp done daily, plus 10 QR posters |
| Target | 1,00,000 | The floor, plus 5 creator collabs and 20 committee or eatery posters |
| Stretch | 5,00,000 | The target, plus one viral Reel, broad committee buy-in and press. Needs the capacity upgrades below first |

The engine is a loop, so every step feeds the next: **see** a post or a forward → **open** a tracked link → **use** it (plan, check in, eat) → **share** (WhatsApp button, story card, My Pujo card) → someone else sees it. The app is built so that each step also creates a share.

---

## 1. What is already built

| Piece | Where | What it does |
|---|---|---|
| Tracked links | `?src=<code>` on any app link | The app remembers the first link that brought a phone, and counts one open per device per day. No sign-in and no personal data. See `supabase/migrations/*_growth.sql` |
| Deep links | `#p=<place id>` | Opens straight onto a pandal or eatery. QR posters, WhatsApp shares and comment replies all use it |
| WhatsApp and share buttons | Every pandal and eatery sheet | Sends a pre-written WhatsApp message with a tracked link (`wa_place`). There is also a system share button (`share`) |
| Story cards | Pandal sheet → 📸 Story card. Me tab → Share my Pujo card | 1080×1920 images for an Instagram story or WhatsApp Status: "I am here", or my pandals, steps and badges (`ig_story`, `ig_mycard`) |
| Link previews | `index.html` Open Graph tags, `icons/og.png` | A pasted link shows a branded card in WhatsApp and Instagram DMs, not a bare URL |
| **Daily content kit** | **https://shubhgptgrowth.github.io/Durga-Puja-2026/kit/** | Every day: an Instagram post (1080×1350), stories (1080×1920), captions in English and Bengali, a WhatsApp Channel post and a forward-ready message. Each has Copy and Download buttons and an "Open WhatsApp" button. Rebuilt every morning at 05:45 IST from the live guide. On puja days at 16:00 it adds "Trending now" cards from live check-ins |
| QR posters | `/kit/posters.pdf` (A4, 69 pages), `/kit/flyer.png` | One poster per top-40 pandal and per eatery: "You are at X. Scan for crowd times, food and the next pandal". The QR is tracked as `qr_<place>` |
| Reach report | Actions → **marketing-report** (21:00 IST daily, plus 09:00 on puja days) | Devices per day, new devices, which link brought them, check-ins, and the busiest places today |
| Instagram auto-posting (optional) | Actions → **marketing-publish** | Posts the day's cards through the official API at 08:15 IST. Off until you set it up (§7) |

The code is in `marketing/`. `kit.py` writes the plan and captions, `render.mjs` makes the images and posters, `report.py` builds the report, and `publish_ig.py` posts to Instagram. The calendar is the `SCHEDULE` dict in `kit.py`. Edit captions there, and the next morning's kit picks them up.

---

## 2. Before the big push: capacity (do this by Mahalaya, 10 Oct)

The free tiers are fine for thousands of users. They are not fine for lakhs.

These are owned by the product track as P0-1 to P0-3 in [ROADMAP.md](../product/ROADMAP.md#p0-launch-blocking). Marketing's job is to make sure they're done before the Mahalaya push.

| Limit | Free plan | What breaks first | Action |
|---|---|---|---|
| **Supabase egress** | 5 GB/month | Live counts are about 12 KB per phone every 3 minutes (already slowed from 90 s). 10,000 phones open for an evening ≈ 2 GB | **Upgrade to Supabase Pro for October** (US$25/month: 250 GB egress, 100k monthly active users, no pausing). Downgrade after Bijoya |
| Supabase monthly active users | 50,000 | Only people who check in or post a moment become users. Opening the app does not (the reach counter uses an anonymous device id on purpose) | Covered by Pro |
| GitHub Pages bandwidth | ~100 GB/month (soft limit) | First load ≈ 0.5 MB compressed, so 1 lakh new phones plus repeat visits ≈ 60–100 GB | For the stretch goal, move hosting to **Cloudflare Pages** (free, no bandwidth cap): connect the repo, output dir `app`. Keep the same paths. Point the QR and links at the new domain by changing `SITE` in `marketing/kit.py` |
| Map tiles (CARTO) | Fair use | Heavy puja-week traffic | Swap to Ola Maps or self-hosted Protomaps (see [MAPS.md](../product/MAPS.md)) |
| A short domain | — | `shubhgptgrowth.github.io/Durga-Puja-2026` is long to say on a poster | Optional: buy something like `pujoparikrama.in` (≈ ₹700/year) and point it at Cloudflare Pages |

---

## 3. One-time setup (about an hour)

1. **Instagram:** create a **professional (Creator or Business) account**: [`@pujoparikrama.guide`](https://www.instagram.com/pujoparikrama.guide/). Display name: "Pujo Parikrama 2026 | Kolkata Pandal Guide" (the name field is searchable).
   * Bio: "Kolkata pandal-hopping guide 2026 · quiet hours · food · routes · ফ্রি".
   * Bio link: `https://shubhgptgrowth.github.io/Durga-Puja-2026/?src=ig_bio`.
   * Make 4 Highlights: North, South, Food, How to use.
2. **Meta Business Suite** (free, on the web or the app): connect the Instagram account. It lets you **schedule posts and stories days ahead**, which is the easiest way to run the calendar without auto-posting.
3. **WhatsApp:**
   * Install **WhatsApp Business** on a dedicated number.
   * Create a **Channel** called "Pujo Parikrama 2026", with the Channel link in the Instagram bio Highlights.
   * Put the Channel invite on the flyer.
4. **Print:**
   * Print `flyer.png` on A5.
   * Print the posters for pandals and eateries where you have permission (§5.3).
5. **Capacity:** do the Supabase Pro upgrade in §2.

---

## 4. The daily routine (15 minutes, 3–22 Oct)

Every morning after 06:00 IST, open **/kit/** on your phone:

1. **Instagram post:** Download → post (or schedule in Business Suite for 12:30 or 19:30) → paste the English caption, then the Bengali one.
2. **Story:** Download → post as a story → add a **Link sticker** with the link shown under the card (`?src=ig_story`). On puja days, also post the "Share your My Pujo card" story.
3. **WhatsApp Channel:** Copy "Channel post" → paste into the Channel.
4. **WhatsApp groups:** "Open WhatsApp" on the forward message → send it to **5–10 groups you belong to**: family, para, housing society, school or college alumni, office. Ask 3 friends to do the same.
5. **WhatsApp Status:** post the story image as your Status.
6. **Replies:** answer comments and DMs with a deep link to the pandal they asked about. Open the pandal in the app → Share → copy.
7. **At 21:00:** read the **marketing-report** run summary, and adjust tomorrow (§6).

On **puja days** (17–21 Oct), repeat steps 1–2 after **16:00**, when the kit adds the live "Trending now" card.

---

## 5. Channel playbooks

### 5.1 Instagram

* **Content pillars:** where to go (area guides, trails), when to go (crowd hacks), what to eat, how to get there, and live (trending, check-in counts). The kit covers all five.
* **Reels:** the kit makes stills, but Reels reach new people. Shoot three on a phone, 15–30 s each, with trending Bengali pujo audio:
  1. *"Sreebhumi without the queue":* show the app's best time, then the near-empty pandal at that hour.
  2. *"16 pandals, 11 km, 16,000 steps":* a time-lapse of the North Heritage trail with the step counter on screen.
  3. *"North or South?":* a split screen of the two area guides, ending "Plan yours, link in bio".
* **Collabs:** use Instagram's Collab post with Kolkata food and travel creators. One post appears on both accounts. Give each creator a code: `?src=creator_<handle>`.
* **Every post:** tag the pandal's location, use the kit hashtags, and post at 12:30 or 19:30.
* **Engagement hooks:** a story poll ("North or South this Ashtami?"), a quiz sticker ("Which pandal won the most check-ins yesterday?"), and reposting users' My Pujo cards. People share what gets reposted.

### 5.2 WhatsApp

* **The Channel** is the broadcast: one daily post from the kit, plus live tips on puja days.
* **Groups are the growth.** Bengali families forward pujo plans. The forward message is written to be forwarded: a short plan, a tracked link, and "Forward to your pujo group 🙏".
* **Status:** the story cards are sized for it.
* **In the app:** every pandal and eatery has a WhatsApp button, so each person who uses it becomes a distributor.
* **Don't:** bulk-message people who haven't opted in, buy contact lists, or add people to groups without asking. WhatsApp bans numbers for this, and it hurts trust.

### 5.3 Offline: QR

* **Where:** puja committee help desks and gates, eatery counters (Mitra Cafe, Golbari, Arsalan…), auto stands, housing society notice boards, college canteens. Metro station exits need Metro Railway permission. Don't post there without it.
* **Always ask** the committee or shop first. Offer them something: their own poster with their name, and a thank-you post after the pujas with their check-in count.
* `posters.pdf` has one page per place, and each QR is tracked as `qr_<place>`. The report shows which posters work. Put more posters near the ones that do.

### 5.4 Partnerships (the multiplier)

| Partner | Their interest | Our offer | Link code |
|---|---|---|---|
| Puja committees | Footfall, fame, crowd management | A spread-the-crowd message ("best time to visit"), their own QR poster, a featured story | `committee_<id>` |
| Eateries | Customers | Featured in food posts and the app, a counter QR | `qr_<id>` |
| Kolkata creators | Content and followers | A Collab post, early access, credit on the kit cards | `creator_<handle>` |
| Housing societies / RWAs | A useful thing for residents | A forward message plus a notice-board flyer | `rwa_<name>` |
| Colleges (NSS / fest teams) | Volunteering and visibility | A "pandal ambassador" shout-out | `college_<name>` |

Any `a-z 0-9 _` code up to 40 characters works. Make one per partner so you can thank the ones who deliver.

---

## 6. Measuring and adjusting

**Link codes**

| Code | Where it's used |
|---|---|
| `ig_bio`, `ig_story` | Instagram bio, story link stickers |
| `ig_mycard` | Links shared with a My Pujo card |
| `wa_channel`, `wa_fwd` | WhatsApp Channel, group forwards |
| `wa_place`, `share`, `plan_share` | In-app WhatsApp, share and route-share buttons |
| `qr_<place>`, `qr_flyer` | Posters and the flyer |
| `creator_*`, `committee_*`, `rwa_*`, `college_*` | Partners |

**Daily decisions (from the 21:00 report)**

* Groups (`wa_fwd`) beat Instagram → spend the time on WhatsApp seeding, and ask more friends to forward.
* A creator code is high → do a second collab with them, and find similar creators.
* A QR poster is high → put more posters in that area.
* Many opens but few check-ins → push "check in so others see the crowd" in stories.
* New devices per day are flat → it's time for a Reel or a creator push, not more of the same posts.

---

## 7. Instagram auto-posting (optional)

Scheduling in Meta Business Suite is enough. For hands-free posting:

1. Make the Instagram account professional (Creator or Business). A Facebook Page is not needed.
2. At developers.facebook.com, create an app (type Business) and add the **Instagram** product.
3. Under **Instagram → API setup with Instagram login**, add the account and **Generate token**. This is a 60-day token that starts with `IG`, with `instagram_business_basic` and `instagram_business_content_publish`. The account's **user id** is shown next to it, or comes from `https://graph.instagram.com/v21.0/me?fields=user_id,username`.
   *Alternative if the account is linked to a Facebook Page:* a long-lived Facebook user token with `instagram_basic`, `instagram_content_publish` and `pages_show_list`, plus the id from `GET /me/accounts` → page → `instagram_business_account`. The script picks the right API from the token.
4. Add the repository **secrets** `IG_USER_ID` and `IG_ACCESS_TOKEN`, and the **variable** `IG_AUTOPUBLISH` = `true`.
5. Test with Actions → marketing-publish → dry run ✔, then a run with dry run unticked.

After that it posts each day's feed post and stories at 08:15 IST, 3–22 Oct, using the images from `/kit/`. Long-lived tokens last about 60 days, which covers the campaign.

**Why WhatsApp isn't automated:**
* WhatsApp Channels have no posting API.
* The WhatsApp Business Platform needs a verified business, pre-approved message templates and opted-in recipients, and charges per message.
* It also can't post into groups.

So the kit makes WhatsApp a two-tap job instead.

---

## 8. Calendar

| Date | Theme | Kit content |
|---|---|---|
| 3 Oct | Launch | What the app does, plus a countdown story |
| 4–7 Oct | Area guides | North, South, Central, East: must-see pandals, nearest metro |
| 8 Oct | Food | Cabins, sweets and rolls near the big pandals |
| 9 Oct | Getting there | Metro, shared autos, buses, park & ride, no-car areas |
| 10 Oct | **Mahalaya** | Launch push: "Devi Paksha begins, plan your pujo". **Do the capacity upgrades before this** |
| 11–15 Oct | Trails | South Heavyweights, North Heritage, Central, Behala, All-Nighter |
| 16 Oct | Panchami | Live: best times, trending (from 16:00) |
| 17–21 Oct | Shashthi → Dashami | Live: best times in the morning, trending from 16:00, My Pujo card stories |
| 22 Oct | Bijoya | Thank-you post with total check-ins, plus "share your card" |

A countdown story runs every day until Shashthi.

---

## 9. Outreach scripts

**Creator DM (English)**
> Hi {name}! We built Pujo Parikrama, a free Kolkata pandal-hopping guide: quiet hours, food, parking, metro and auto routes, and live check-ins for 107 pandals. Would you try it on one of your pujo outings and do a Collab post? Your followers get a personal link (shubhgptgrowth.github.io/Durga-Puja-2026/?src=creator_{handle}), and we'll feature your Reel in our stories. 🙏

**Creator DM (Bengali)**
> নমস্কার {name}! আমরা "পুজো পরিক্রমা" বানিয়েছি, কলকাতার ঠাকুর দেখার একটা ফ্রি গাইড। ১০৭টা প্যান্ডেল, কখন ভিড় কম, খাবার, পার্কিং, মেট্রো-অটো রুট আর লাইভ চেক-ইন আছে। আপনার পুজো ঘোরার একদিন একবার ব্যবহার করে একটা Collab পোস্ট করবেন? আপনার জন্য আলাদা লিংক থাকবে, আর আপনার রিল আমাদের স্টোরিতে দেব। 🙏

**Puja committee**
> Namaskar! Pujo Parikrama is a free guide that tells visitors the best time to visit each pandal, which spreads the crowd. {pandal} is already listed. Could we put up a QR poster at your help desk? It opens your pandal's page, with directions, the nearest metro and food nearby. After Bijoya, we'll share how many visitors checked in at {pandal}.

**Housing society / office group**
> 🪔 For this pujo: a free app that plans pandal hopping by area. It shows when each pandal is quietest, where to eat and park, and the metro, bus and auto routes. It works in Bengali too. {link with ?src=rwa_name}

---

## 10. Ground rules

* The kit cards credit every Wikimedia Commons photo, which the CC licences require. Don't crop the credit out.
* Don't use a committee's logo, or a professional photographer's idol photos, without permission.
* The app never asks for a phone number or name. Keep it that way in every message ("free, no sign-up").
* Paid boosts are optional, and only worth it once organic growth flattens. If you run one, boost a proven Reel, target Kolkata and Howrah, ages 18–45, at a small daily budget, and give it its own code (`ig_ad`).
