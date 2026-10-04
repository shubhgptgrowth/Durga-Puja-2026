# Contacts repository

People can add a name and mobile number in **My Pujo**. The name always stays on the phone (it goes on their
story cards). The name and number reach us only if they tick *"Send my number to the Pujo Parikrama team for
pujo updates"*. This page covers what we then keep, where, and how the team gets at it.

## What is stored (Supabase, project `wmvzakyqnwfekyhjkprp`)

| Table | Holds | Readable by |
|---|---|---|
| `profiles` | name, phone (`+91…`), language, the link that first brought them, device id, opt-in and update times | service role only |
| `consent_log` | granted / updated / withdrawn + time, per anonymous user id (no name, no phone) | service role only |

`contacts_report()` joins each opted-in person with data points the app already collects anonymously:
days the app was opened, last open, pandals checked in at, eateries, ratings given and their average, last
visit. `contacts_summary()` gives counts only. Neither can be called with the app's public key (tests in
`tests/sql/contacts_test.sql` check this).

Unticking the box deletes the `profiles` row immediately; `consent_log` keeps a "withdrawn" entry so we can
show consent was honoured.

## Getting the list

The repo is **public**: workflow logs and artifacts can be read by any signed-in GitHub user. So:

1. One-time: add a repository secret **`CONTACTS_PASSPHRASE`** (Settings → Secrets and variables → Actions),
   a long random passphrase shared only with the people who may see the list.
2. Actions → **contacts-export** → *Run workflow* (it also runs daily at 22:15 IST). The run summary shows
   counts only. The list is attached as `contacts-encrypted` (kept 3 days).
3. Download, unzip, then:
   ```
   openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in contacts.csv.enc -out contacts.csv
   ```

Without the secret the workflow still runs and reports counts, but exports no list.

Columns: `name, phone, lang, first_src, opted_in, updated, days_active, last_open, pandals, eateries, ratings,
avg_stars, last_visit`.

## Rules for using it (DPDP Act 2023)

- **Purpose is pujo updates.** People agreed to that and nothing else. Don't sell or share the list, and
  don't use it for unrelated marketing without asking them again.
- Keep downloaded copies off shared drives; delete them after use.
- **Deletion requests** that come in by message: run
  `delete from profiles where phone = '+91XXXXXXXXXX';` in the Supabase SQL editor, and log it.
- **Retention:** plan to delete the list after the season (suggested: 31 Jan 2027) unless people opt in again
  for next year.
