# Steps from Apple Health (iPhone Shortcut)

Websites can't read Apple Health, so the app takes steps through a link that a Shortcut opens:

```
https://shubhgptgrowth.github.io/Durga-Puja-2026/?src=ios_shortcut#steps=8432
https://shubhgptgrowth.github.io/Durga-Puja-2026/?src=ios_shortcut#steps=8432&date=2026-10-18
```

The app saves the number as that day's Health steps (`dayRec(date).health`), shows the higher of it and what
the app tracked itself, and lands on My Pujo. Numbers like `8,432` or `8432.0` are fine; values are capped at
100,000. A `date` is optional (default today) and can't be in the future. `?src=ios_shortcut` lets the reach
report count how many people use it.

## Build the Shortcut (about 2 minutes)

1. Shortcuts app → **+** → *Add Action* → **Find Health Samples**
   - Type: **Steps**, filter **Start Date is Today**, **Group By: Day**.
2. **Calculate Statistics** → **Sum** of *Health Samples*.
3. **URL** → paste `https://shubhgptgrowth.github.io/Durga-Puja-2026/?src=ios_shortcut#steps=` and insert the
   *Statistics* variable at the end.
4. **Open URLs**.
5. Name it **Pujo steps**, pick an icon (🥁), *Add to Home Screen*.

Optional, automatic: Shortcuts → **Automation** → *Time of Day* 11:00 pm, daily → *Run Immediately* → run
**Pujo steps**. (iOS opens Safari when it runs.)

The same steps are written out in the app (My Pujo → "Add steps from your Health app or watch"), with a copy
button for the link.

## One-tap install (the ready-made Shortcut)

`scripts/make_shortcut.py` builds the Shortcut above as a file. iOS only installs **signed** Shortcuts, and
Apple only signs on a Mac that is **signed into iCloud**. GitHub's Macs aren't, so the `shortcut` workflow
attaches the unsigned file to its run and stops there. To finish, on any Mac with this repo:

```
scripts/sign_shortcut.sh      # builds, signs (shortcuts sign --mode anyone), points app/config.js at it
git add app/shortcut app/config.js && git commit -m "Signed Pujo steps Shortcut" && git push
```

My Pujo then shows **Add the "Pujo steps" Shortcut** on iPhones: one tap opens it in the Shortcuts app.
Before announcing it, run it once on an iPhone (Health asks for permission the first time) and check that
the app opens with today's steps.

No Mac? Build the Shortcut on an iPhone (steps above), then Share → **Copy iCloud Link**, and put that
link in `app/config.js` as `healthShortcut`. Same result.

## Notes

- **Phone + Apple Watch:** "Find Health Samples → Sum" can count the same walk twice when both devices record
  it (Health's own total de-duplicates; the raw samples don't). If the number looks high, add a filter in step 1:
  **Source is** your iPhone (or your Watch), so only one device counts.
- **Android:** no equivalent. Health Connect and Google Fit have no web API, so Android users type the number
  in (or the app's own motion-sensor count is used).
- Nothing leaves the phone: the number stays in the browser's local storage like the rest of My Pujo.
