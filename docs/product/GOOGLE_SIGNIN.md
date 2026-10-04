# Google sign-in (My Pujo on every phone)

**What it does:** My Pujo shows **Continue with Google**. The first time, the browser's guest account is
*linked* to Google, so it keeps the same user: check-ins, ratings, photos and the progress backup all stay.
On any other phone or browser, **Continue with Google** signs in to that same account. Steps, pandals,
food stops and badges come back on their own and are merged with anything already on that phone.
**Sign out** saves first, then this browser forgets the pujo; it's still in the Google account.
The Pujo code (and its link) still works for people who'd rather not sign in.

The button only appears once Google sign-in is on in Supabase. It costs nothing.

## One-time setup (about 10 minutes)

1. **Google Cloud project.** Go to <https://console.cloud.google.com/> and choose **Select a project → New project**.
   Name it `Pujo Parikrama` and click **Create**, then select it.
2. **Consent screen.** Go to **APIs & Services → OAuth consent screen**, shown as *Google Auth Platform* in newer consoles, and click **Get started**.
   - App name: `Pujo Parikrama`. User support email: your email.
   - Audience: **External**. Contact email: your email. Agree, then **Create**.
   - **Branding → Authorized domains:** add `wmvzakyqnwfekyhjkprp.supabase.co` and `shubhgptgrowth.github.io`. Save.
   - Logo is optional, and leaving it out avoids Google's brand review. If the console insists, use
     `pujo-parikrama-logo-120.png` (in this folder, 120×120).
   - **Audience → Publish app**, then confirm. Without this, only "test users" you list can sign in.
     The app only asks for name and email (`openid`, `email`, `profile`), so Google doesn't need to review it.
3. **The key (OAuth client).** Go to **Clients**, or **Credentials → Create credentials → OAuth client ID**.
   - Application type: **Web application**. Name: `Pujo Parikrama web`.
   - Authorised JavaScript origins: `https://shubhgptgrowth.github.io`
   - Authorised redirect URIs: `https://wmvzakyqnwfekyhjkprp.supabase.co/auth/v1/callback`
   - Click **Create**, then copy the **Client ID** and **Client secret**.
4. **Give them to the repo.** In GitHub, go to the repo's **Settings → Secrets and variables → Actions → New repository secret**:
   - `GOOGLE_CLIENT_ID`: the Client ID
   - `GOOGLE_CLIENT_SECRET`: the Client secret
5. **Switch it on.** Go to **Actions → supabase-setup → Run workflow**, with project ref `wmvzakyqnwfekyhjkprp`.
   The run turns on Google sign-in and account linking, and allows the app's URL as a return address.
   Its summary says **Google sign-in is on**.
6. **Try it.** Open the app, then **My Pujo → Continue with Google**. Then open the app in another browser and sign in again.
   Your progress should be there.

## Notes

- Google's screen says "to continue to wmvzakyqnwfekyhjkprp.supabase.co". Showing the app's own name there needs a custom
  domain on Supabase, which is a paid add-on. Sign-in works either way.
- If the app moves to a custom domain (HOSTING.md), re-run supabase-setup with `site_url` set to the new address. Also add
  that origin in step 3.
- Under the hood: `community.signInWithGoogle()` links the guest account (`/auth/v1/user/identities/authorize`). If that
  Google account is already linked to someone, it falls back to a plain sign-in (`/auth/v1/authorize`).
  `community.authReturn()` reads the tokens on return and tidies the URL. `sync.js` then pulls the account's backup and merges it in.
  The e2e test runs both paths against the fake backend.
