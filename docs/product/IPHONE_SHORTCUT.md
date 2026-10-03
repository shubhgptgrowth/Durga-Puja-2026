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

## Sharing one ready-made Shortcut

To give people a one-tap install instead: build the Shortcut above on an iPhone, then Share → **Copy iCloud
Link**, and put the link in `app/config.js` as `healthShortcut`. My Pujo then shows an **Add the "Pujo steps"
Shortcut** button instead of the build steps.

## Notes

- **Phone + Apple Watch:** "Find Health Samples → Sum" can count the same walk twice when both devices record
  it. Health's own total de-duplicates; if numbers look high, swap steps 1–2 for **Get Health Quantity**-style
  actions where available on your iOS, or filter Source to one device.
- **Android:** no equivalent. Health Connect and Google Fit have no web API, so Android users type the number
  in (or the app's own motion-sensor count is used).
- Nothing leaves the phone: the number stays in the browser's local storage like the rest of My Pujo.
