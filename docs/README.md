# Pujo Parikrama 2026: docs

The work runs in two tracks.

| | 1. Product development | 2. Marketing |
|---|---|---|
| **Goal** | The app at [shubhgptgrowth.github.io/Durga-Puja-2026](https://shubhgptgrowth.github.io/Durga-Puja-2026/) is accurate, fast and reliable through puja week | Every pandal hopper in Kolkata opens it at least once, via Instagram, WhatsApp, QR and partners |
| **Start here** | [product/ROADMAP.md](product/ROADMAP.md): key dates, backlog (P0/P1/P2), how a change ships | [marketing/PLAN.md](marketing/PLAN.md): the playbook · [marketing/TRACKER.md](marketing/TRACKER.md): owners, daily log, partners, targets |
| **Reference** | [product/SCOPE.md](product/SCOPE.md) (features, data model) · [product/COMMUNITY.md](product/COMMUNITY.md) (backend) · [product/MAPS.md](product/MAPS.md) (map providers) | [`/kit/`](https://shubhgptgrowth.github.io/Durga-Puja-2026/kit/) (daily content) · Actions → **marketing-report** (reach) |
| **Code** | `app/`, `pipeline/`, `data/`, `supabase/`, `tests/` | `marketing/` |
| **Workflows** | `pipeline`, `deploy`, `discover`, `geo-audit`, `supabase-setup` | `marketing-report`, `marketing-publish` (the kit itself is built inside `deploy`) |
| **Measure of success** | Pins correct, no outages, check-ins working, pages fast on a crowded network | Devices reached, by source; check-ins per device |

**Where the tracks meet:**
* Marketing links depend on the app's `?src=` codes, `#p=` place links, place ids and share buttons. These are listed in [ROADMAP.md → What marketing relies on](product/ROADMAP.md#what-marketing-relies-on-the-seam).
* Marketing asks for app changes in [TRACKER.md §5](marketing/TRACKER.md#5-asks-for-the-product-track). Product accepts them into its backlog.
