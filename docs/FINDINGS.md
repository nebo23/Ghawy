# Ghawy — Findings Log

Things noticed outside the scope of the phase that was running. Logged here and
carried on with, per the "when in doubt" rule. Nothing in this file has been
acted on.

---

## Opened in Phase 0

### F-00 · The fabricated guest endorsements are LIVE and PUBLIC — `CRITICAL`

Escalation of the known seed-data issue. This is not confined to `seed_defaults()`
in `backend/main.py:52-90` — **the rows are in the production database and are
served to anyone on the internet without a token.**

```
$ curl -H "Host: ghawy.ai" https://localhost/api/guests/     # no Authorization header
200
[{"id":35,"name":"Lex Fridman","title":"AI Researcher","company":"MIT",
  "is_featured":true,"sessions_count":6,"attendees_count":8000,"rating":4.9,
  "sessions":[{"title":"Live Session with Lex Fridman",
               "session_date":"2026-07-14T19:47:20","status":"upcoming"}]}, …]
```

Production `guests` table, ids 33–37, all `is_featured = true`:

| Name | sessions | attendees | rating |
|---|---:|---:|---:|
| Sam Altman | 12 | 15,000 | 4.9 |
| Sundar Pichai | 8 | 12,000 | 4.8 |
| Lex Fridman | 6 | 8,000 | 4.9 |
| Fei-Fei Li | 5 | 6,000 | 4.8 |
| Mark Zuckerberg | 4 | 10,000 | 4.7 |

Each has a matching `guest_sessions` row titled "Live Session with &lt;name&gt;",
still `status = upcoming`, dated `2026-07-14` — a date now seven weeks in the
past, so the site is currently advertising a *lapsed* future session with these
people.

Every number is invented. Read plainly, the platform publicly claims that five
real, named, identifiable individuals have appeared as guests, states how many
sessions each ran, how many people attended, and what audiences rated them, and
announces another session to come.

**Why this is logged rather than fixed here.** Phase 0 changes no logic and
deletes nothing, and Phase 2 owns the remedy — for the code *and* for the
production rows, since removing the seed function does not remove data already
written. Two things follow for Phase 2:

* the cleanup script must cover `guests` **and** the dependent `guest_sessions`
  rows, and it is to be staged for the owner, not executed;
* `GET /guests/` being unauthenticated is a separate question for Phase 3 — but
  note that authenticating it would only narrow the audience, not fix the claim.

This is the highest-severity item found in Phase 0. If any part of the audit is
worth pulling forward out of order, it is this one — that decision is the
owner's.


### F-01 · The landing page polls a third-party Supabase project — `HIGH`

`frontend/src/js/main.js:136` and `:253`. `checkPurchases` (every 5s) and
`fetchLastPurchase` (every 10s) both `fetch` from
`https://opetjxxzbmqzmqouqare.supabase.co/rest/v1/purchases`, with a publishable
API key hardcoded in the JavaScript. They drive the "someone just bought" popup
and the progress bar on `index.html`.

Neither touches Ghawy's backend. So the reported concern — polling load on this
server — does not exist. What does exist:

* an **undocumented third-party runtime dependency** on the public landing page:
  if that Supabase project goes away, the landing page's social proof breaks
* a table of purchase records (names, timestamps) living **outside this system**
* every visitor issuing 12 requests/minute to a third party for the whole time
  the tab is open
* a credential in the repository — publishable, so low severity in itself, but
  it grants whatever that project's row-level security permits, which has not
  been checked

Also unknown: whether that data is real, and whether the named people consented.
That question is adjacent to Phase 2 and should be answered with it.

**Owner decision needed.** For Phase 4.

### F-02 · A lesson has a corrupt VdoCipher video id — `MEDIUM`

Production logs, 4 occurrences:

```
ERROR app.services.vdocipher: VdoCipher OTP generation failed for video d.
Status: 400, Body: {"message":"Invalid videoId found"}
```

A lesson's `vdo_video_id` is the single character `d`. Members opening that
lesson get a video that will not play. Needs a `SELECT` to find the row, then a
correction — a data fix, not a code fix. Out of Phase 0 scope (read-only).

### F-03 · An orphan table in the production database — `LOW`

`subscription_repair_2026_08_14` exists in the production database and is
declared by no model and no migration — a leftover from a dated repair. Harmless
but it makes the schema misleading, and it will confuse the Phase 1 work on
`create_all`. Decide in Phase 1 whether to drop it or document it.

### F-04 · `user_course_progress` is dead but still queried — `LOW`

The table is empty and nothing writes to it; learners are derived from
`lesson_playback_grants ∪ user_progress`. It is nonetheless still referenced by
`admin.py` and `dashboard.py`, so any aggregate built on it reads as zero. Worth
confirming no dashboard number is silently zero because of it. For Phase 4/5.

### F-05 · Three pages still load Tailwind from a CDN — `LOW`

`register.html`, `privacy.html` and `terms.html` load
`https://cdn.tailwindcss.com`; `index.html` loads `https://cdn.plyr.io`. Vendor
libraries were deliberately self-hosted precisely because a CDN dependency has
caused icons to vanish before. These are the remaining exceptions. `register.html`
is a conversion-critical page. For Phase 5.

### F-06 · A dated secrets backup sits in the tree — `MEDIUM`

`backend/.env.production.bak.1783362291`, mode 0600, unreferenced. It is not in
git (`.env*` is ignored), so this is a local-disk exposure rather than a
repository one. Deleting a secrets file is the owner's call, not an agent's.
Confirm in Phase 3 whether the credentials it holds are still valid — a stale
backup of *rotated* secrets is harmless; a stale backup of *current* secrets is
a second copy of the crown jewels.

### F-07 · Two unreferenced compose files — `LOW`

`docker-compose.test.yml` (165 B) at the root and `backend/docker-compose.yml`
are both referenced by nothing. Neither is the deployed topology
(`docker-compose.prod.yml` is). Both `UNKNOWN` — a developer may run one by
hand. For Phase 5.

### F-08 · The baseline cannot cover authenticated behaviour — `PROCESS`

No browser binary exists on this host, so [`BASELINE.md`](BASELINE.md) captures
anonymous HTML only: no screenshots, no console errors, no logged-in page
behaviour. Phase 3 and Phase 6 both have acceptance gates that require exactly
those things ("no new console errors", "chat fully working: send, live receive,
reactions, attachments, mentions, read receipts").

**Those gates cannot be honestly signed off with what is installed today.**
Before Phase 3, one of: install a headless browser here, or run the checks from
a workstation against staging, or accept the gates as manually verified by the
owner. Flagging now rather than discovering it at the gate.

### F-09 · A third destructive script the brief did not list — `RESOLVED in Phase 0`

The brief named `test_security_acceptance.py` and `test_atlas_promo_and_reset.py`
as the destructive files. **`test_team_roles.py` was a third**, carrying the
identical `DROP SCHEMA public CASCADE` at line 33 — added recently, in commit
`d24c7a9` on this branch. All three were moved and guarded together.

The lesson is procedural: the danger is the *pattern*, and the pattern is being
copied into each new acceptance script. The guard in
`backend/scripts/_acceptance_guard.py` and the note in
`backend/scripts/README.md` are what stop the next copy from being unguarded.

### F-10 · 30-day JWTs with no refresh mechanism — `MEDIUM`

`users.py:39` — `ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30`. A stolen token is
valid for a month. There is a `token_version` claim that allows server-side
invalidation, so the mitigation exists; what is not established is whether
anything actually bumps it on password reset or logout. For Phase 3.

### F-11 · `backend/.env` was committed to git history — `HIGH`

`.gitignore` now covers it, but the ignore rule came after the fact:

```
$ git log --all --diff-filter=A -- backend/.env
5ff4058 Done
f5be627 Done
```

The file was added to the repository twice and is still recoverable from history
by anyone with a clone. `backend/.env.production.example` is in history too, but
that one is intended to be.

An ignore rule does not retract a published secret. The only fix is rotation —
of every credential that file has ever held: database password, `SECRET_KEY`
(which signs the 30-day JWTs), Kashier keys, SMTP credentials, VdoCipher and
Bunny keys, Google OAuth secret.

Rotating `SECRET_KEY` invalidates every issued token and logs every member out
at once, so it needs to be planned rather than done casually. That planning is
Phase 3's, and the decision is the owner's.
