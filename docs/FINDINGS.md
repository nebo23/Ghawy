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

### F-03 · An orphan table in the production database — `LOW`, ANSWERED in Phase 1

`subscription_repair_2026_08_14` exists in the production database and is
declared by no model and no migration — a leftover from a dated repair.

Phase 1 was asked to decide. It investigated rather than dropped, and the answer
is **keep it, reclassified as data**:

| Question | Answer |
|---|---|
| Does it hold rows? | Yes — **2**. |
| Does anything read it? | No. A full-repo search over `.py`, `.js`, `.html`, `.sql`, `.sh`, `.md` finds zero references outside `docs/`. |
| When was it last written? | `2026-08-14 12:17:11` — both rows in one transaction. Never written since. |
| Size on disk | 32 kB |

| user_id | old_end_at | new_end_at | days_added |
|---:|---|---|---:|
| 591 | 2026-08-30 17:16:00 | 2026-08-31 18:07:01 | 1.0354 |
| 884 | 2026-11-15 10:53:58 | 2026-11-15 16:41:41 | 0.2415 |

Both users still exist and **both repairs are still intact** — each account's
current `users.end_at` still equals the `new_end_at` recorded here, so nothing
has overwritten the correction. User 591's subscription has since lapsed
(`is_active = false`), which is expected: the repair added a day back in August.

So the table is a hand-written audit record of a manual correction to two paying
members' subscriptions, and the only surviving record of what the values were
beforehand. It is **data, not dead code** — it is not a Phase 5 deletion
candidate and must never be classified `UNUSED`.

`ghawy_baseline` deliberately does not create it, so a clean database will not
have it. If a later phase wants the schema tidy, archive both rows to a file
first and record the path here.

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

---

## Opened in Phase 1

> Numbering continues from F-11. An earlier draft of this section restarted at
> F-10 and collided with two Phase 0 findings; the duplicate orphan-table entry
> was folded into F-03 above, where it belonged.

### F-12 · Three constraint/index names differ between production and the models — `COSMETIC`

Functionally identical, so `ghawy_baseline` was left matching the models rather
than renaming anything on a live database:

| Object | Production | Models / a clean install |
|---|---|---|
| `admin_member_notes.member_id` | plain index + `admin_member_notes_member_id_key UNIQUE` | one `UNIQUE INDEX` |
| `coupons.code` | plain index + `uq_coupons_code UNIQUE` | one `UNIQUE INDEX` |
| `exams.after_lesson_id` FK | `fk_exams_after_lesson_id_lessons` | `exams_after_lesson_id_fkey` |

Both shapes enforce the same uniqueness and support the same lookups. Worth
knowing only if a future migration tries to drop one of them *by name* — it must
use the production name, not the autogenerated one.

### F-13 · Six revisions have an empty `upgrade()` — `INFORMATIONAL`

Five are autogenerated revisions that found nothing to do, because `create_all`
had already made the table named in their title: `2334af3cafbd` (daily_reports),
`234cce29f5f4` (ai_updates), `307efdf1db45` (notifications), `920b33de7a7e`
(suggested_guests), `a50de1dd7efd` (feedbacks).

The sixth is the merge `4823c6c0b288`, which is empty because that is what a
merge revision is — it joins two branches and applies nothing. Not a defect, and
not counted with the other five.

All six are kept: deleting a revision rewrites history for every database
stamped past it, and they cost one no-op each. `ghawy_baseline` creates those
five tables now.

### F-14 · `# Force Reload` / `# reload` left at the bottom of `main.py` — `TRIVIAL`

Two stray comments at the end of the file, left over from a deploy that needed
the file to change. Harmless. Left for the Phase 5 comment pass.

### F-15 · `aaa10e9ec801`'s `downgrade()` is broken — `LOW`

Found while building the legacy-replay verification. Downgrading past
`aaa10e9ec801_remove_recurring_and_add_end_at` fails:

```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedObject)
type "projectsubmissionstatus" does not exist
[SQL: ALTER TABLE project_submissions ALTER COLUMN status TYPE projectsubmissionstatus]
```

Its `upgrade()` converts `project_submissions.status` from a Postgres enum to a
String; the `downgrade()` at line 70 converts it back, but nothing recreates the
enum type first — and in production that type never existed at all, because
`create_all` made the column a String from the start.

**Pre-existing and unrelated to Phase 1** — the guard added in Phase 1 returns
early only when the baseline marker is present, and this fails on databases that
have no marker, i.e. with the original code running unchanged.

Consequence: the history can be downgraded from head as far as `aaa10e9ec801`
(33 revisions) but no further. Not fixed here — it is out of Phase 1 scope, and
downgrading a production database 34 revisions is not an operation anyone should
be reaching for. Fix it by recreating the enum type in the `downgrade()` before
the `ALTER`, if a later phase wants the chain fully reversible.

### F-16 · An unstamped database with tables cannot be upgraded — `INFORMATIONAL`

If a database has the schema but no `alembic_version` row (someone's old
`create_all` database, or a restore that skipped the table),
`alembic upgrade head` fails on the first real revision:

```
psycopg2.errors.DuplicateColumn: column "video_status" of relation "lessons" already exists
```

This is correct behaviour, not a regression — verified that `ghawy_baseline`
no-ops and writes **no marker** in this case, so the historical revisions run
for real, exactly as they did before Phase 1 existed. Alembic simply cannot
infer where an unstamped database sits in the history.

The supported recovery is `alembic stamp <the revision that matches the schema>`
— `alembic stamp head` when the schema is current. Verified: after stamping,
`upgrade head` is a clean no-op and all 1912 users are untouched.

---

## Opened in Phase 2

### F-17 · Sixteen dead model imports in `main.py` — `TRIVIAL`

`main.py` imports 26 names from `app.models`; only `User` and `Payment` are
used. Phase 2 removed the eight it orphaned itself (`Category`, `Channel`,
`ChannelType`, `Course`, `Lesson`, `Guest`, `GuestSession`, `Coupon` — they moved
to `app/seed.py` with the seed code) and left the other sixteen, which were
already unused before this phase:

```
ChatMember  MemberRole  MessageRead  Message  PostReaction  CommentReaction
ManualPaymentRequest  LiveAttendee  LiveSession  AiUpdatePost  AiUpdatePoll
AiUpdatePollOption  AiUpdatePollVote  AiUpdateReaction  AiUpdateComment
CommunityFeedback
```

Left deliberately rather than swept up: they are pre-existing and belong to the
Phase 5 cleanup pass, not to a seed-data phase. Zero runtime cost beyond the
import.

### F-18 · The fabricated guest rows were self-healing — `CONTEXT for F-00`

Not a new defect, but the mechanism was not recorded and it changes the order of
operations for the fix. The seed guard was:

```python
if db.query(Guest).count() == 0:
```

so **deleting the fabricated guests did not remove them** — the next restart put
them straight back. Production's `guests_id_seq` sits at `37` while holding only
5 rows (ids 33–37), which is the fingerprint of that loop having run more than
once against an emptied table.

Consequence for the cleanup: the Phase 2 backend must be **deployed first**, and
only then may `scripts/cleanup_seeded_public_figures.py` run. Run in the other
order and the rows come back on the next boot. Verified: after deleting the rows
on a production clone and booting the Phase 2 code, `guests = 0` and
`guest_sessions = 0` — they stay gone.

---

### F-19 · Account enumeration on `/login` — `PHASE 3, left for the owner's decision`

`/auth/login` returns three distinguishable outcomes: 400 "use the Google button"
(registered via Google), 403 "verify your email" (registered, unverified), 401
(wrong password *or* no such account). A nonexistent address also returns faster,
because `if not user or not verify_password(...)` short-circuits before bcrypt.

Not fixed in Phase 3 because the Google message is deliberate UX, and collapsing
the responses degrades it. Rate-limited at 30r/m. Needs a product decision, not a
security one.

### F-20 · `_send_lock` is per-process — `PHASE 3, informational`

`announcements.py` guards real sends with a `threading.Lock`. Correct on this
deployment (one gunicorn worker) and it holds today, but it would not serialise
across `--workers N`. If the worker count ever rises, the single-send guarantee
becomes the `status == "sent"` check alone. Recorded so that is a known
consequence rather than a surprise.

### F-21 · Geo-lookup interpolates a client header into a URL path — `PHASE 3, informational`

`google_auth.py:96` builds `https://ipapi.co/{ip}/json/` where `ip` comes from
`X-Forwarded-For`. Not SSRF: scheme and host are literal, so the request cannot
be steered off `ipapi.co`, and urllib rejects control characters. Cosmetic only.

### F-22 · `GET /courses/{id}/reviews` ignores `is_published` — `PHASE 3, informational`

Every other public course path filters `is_published == True`; this one resolves
the course by id alone, so reviews attached to an unpublished course are
readable. Content is review text plus reviewer display name and avatar. Low
value, but it is an inconsistency in a rule the rest of the file applies.

### F-23 · Avatar loads trip the per-IP rate limit — `observed during the Phase 3 deploy, for PHASE 4`

`GET /api/uploads/avatars/…` and `/api/static/avatars/…` return 429 in bursts:
41 occurrences from 2 IPs in the 12 minutes after the Phase 3 deploy, and **53
in the equivalent window before it** — so this is pre-existing and unrelated to
the security fixes, not a regression.

Cause is shape, not abuse: a chat or members page renders many avatars at once
and a single browser exceeds the `api` zone (30r/s, burst 20) on its own image
requests. The member sees broken avatars.

Belongs to Phase 4. Options worth weighing there: serve avatars from a location
with its own (or no) limit since they are public static files already excluded
from auth, raise the burst, or sprite/lazy-load them. Do not simply raise the
global `api` rate — that zone is what absorbed the July abuse swarm.

### F-24 · Supabase purchases table was world-writable — `AWAITING CONFIRMATION that the project is deleted`

**Status (2026-09-03): two of the three removals are done. The third — the one
that actually closes the exposure — is with the owner.** Do not mark this
resolved until the Supabase project is confirmed deleted; until then the table
is still reachable by anyone holding the key.

The owner's starting belief was that there was **no Supabase project at all**.
The probes below are what showed otherwise, and that is why this finding
mattered: nobody was going to close an exposure they did not believe existed.
Deleting the project is a stronger fix than enabling RLS, because it removes the
data and the endpoint together rather than restricting access to them.

What this was: `frontend/src/js/main.js` carried a hardcoded Supabase
publishable key for a landing-page purchase ticker. Checking the premise rather
than the key — a publishable key is meant to be public, so its presence in the
source was never the flaw — RLS was not enforcing on the table at all:

    GET    /rest/v1/purchases?select=*   → 200, 238 rows
    DELETE /rest/v1/purchases?id=eq.-1   → 204
    PATCH  /rest/v1/purchases?id=eq.-1   → 204

Both write probes used a filter matching no rows and the count was 238 before
and after, so nothing was altered. But 204 means the operation was permitted;
the same key with `?id=gt.0` would have emptied the table. So the severity was
never "238 first names are readable" but "anyone can destroy or forge the
purchase record".

**Three separate removals, and this is the lesson worth keeping.** They looked
like one job and were not:

1. **The polling code** — removed in `41bfd21`. ✅ It fetched a row every 10s for an element that exists on no page.
2. **The CSP allowance** — `https://*.supabase.co` removed from `connect-src` in both headers, `ca8b757`. ✅ It had outlived its only caller by surviving step 1 entirely: an allowance for a service nothing calls is a standing permission with no user, still reachable by an injected script.
3. **The project itself** — ⏳ with the owner. Only this one closes the write exposure.

After step 1 the feature looked gone. After step 2 the permission looked gone.
**The data was still world-writable through the whole of both.** Deleting the
caller does not revoke the permission, and removing the permission does not
close the endpoint — the browser was never the only way to reach it. Anyone with
the key could `curl` the REST API directly no matter what our CSP said, because
CSP constrains *our pages*, not the service.

So when retiring an integration, treat it as three questions, not one: is the
code gone, is the permission gone, and is the *thing itself* gone. Two of those
can be true while the risk is entirely unchanged.

⚠️ **The publishable key is burned regardless, and permanently.** It sits in this
repository's git history, which is not being rewritten. Deleting the project
makes the key point at nothing, which is why this is resolved — but **if that
Supabase project is ever recreated, or another one is created for this site, it
must use a new key**. Reusing the old one restores a credential that has been
public since it was committed. The same caution applies to any other project in
that Supabase organisation if the key was ever shared across them.

### F-25 · `#stickyCta` handler binds to an element that does not exist — `PHASE 5`

`main.js` does `document.getElementById("stickyCta")` and attaches a scroll
handler; no element with that id exists in `index.html` or in the rendered live
page. Same class as the live-purchase widget, but it costs no requests — it is
an inert scroll listener, not a poll. Left alone deliberately: dead frontend
code is Phase 5's scope, not Phase 4's, and this phase is about request and
query load.

### F-26 · `/profile/me` is fetched three times per page from `utils.js` — `PHASE 4, proposed and stopped`

Measured in the browser on the dashboard: 3 × `GET /api/profile/me` per load.
All three come from `utils.js`, so this repeats on all 13 pages that load it.

The shared in-flight promise used for `/dashboard/summary` would collapse them,
but the three call sites do **not** behave the same way on failure:

    utils.js:257   401 → clear token+user, redirect to /login
    utils.js:321   401 → logout(); 402 → redirect to /renewal; returns null
    utils.js:412   only reads is_admin; no error handling at all

Sharing one promise hands whichever call ran first the deciding vote on the auth
guard and the renewal redirect, on every page. That is a functional risk out of
proportion to two saved requests per load.

If it is taken up: keep the three failure paths intact and share only the
*successful* payload — resolve a promise carrying the parsed user plus its
status, and let each caller apply its own handling. Verify against a 401 and a
402 account on a members page and on `/renewal` itself before shipping. Do not
fold the guards together.

### F-27 · GA4 is being blocked by our own CSP — `found during the connect-src audit, PRE-EXISTING`

Rendering the landing page in a browser after the Supabase removal surfaced a
violation that has nothing to do with it:

    Refused to connect to 'https://stats.g.doubleclick.net/g/collect?v=2&tid=G-…'
    because it violates … connect-src

`stats.g.doubleclick.net` is absent from both the old and the new policy, so this
is pre-existing and not a regression — but it means GA4's Google-Signals /
remarketing beacon has been silently dropped for as long as the CSP has been
enforcing. Analytics still work; this specific collection call does not.

**Decided (2026-09-03): turn Google Signals off in the GA4 property. Do not add
`stats.g.doubleclick.net` to the CSP.** Removing the request beats permitting
it — the beacon stops being attempted at all rather than being allowed through,
and it needs no CSP change, so there is nothing to deploy and nothing to keep
in sync between the repo and the server.

**This is an owner action in the GA4 admin console, not a code change.** Nothing
in this repository can do it, and no follow-up here is pending: recorded, not
chased. Until it is actioned the only effect is that this one collection call
keeps being blocked, which is the current behaviour anyway — the CSP has been
dropping it for as long as it has been enforcing. Ordinary GA4 analytics are
unaffected.

For the record, the rejected alternative was adding the origin to `connect-src`
in both headers. It was rejected on principle rather than effort: it is an
ads-network host, and permitting one to satisfy a beacon nobody asked for is the
wrong direction for a policy whose whole value is that it is narrow.

Worth also noting what the audit *confirmed* rather than changed: the
report-only header correctly reports every inline `<script>` as a violation.
That is its stated job — it is the next policy, without `'unsafe-inline'` — so
those reports are the to-do list for that migration, not a fault.

### F-28 · CSP origins that a source grep cannot clear — `method note for future audits`

Auditing `connect-src`/`script-src`/`frame-src` by grepping the repo gives the
wrong answer for four classes of origin, and every one of them appeared in this
audit with **zero source hits** while being genuinely required:

  * **Stored in the database** — `player.mediadelivery.net` has no reference in
    any file, but an AI Updates post's `media` column points at it. Found by
    querying the column, not the tree.
  * **Generated server-side** — `payments.kashier.io` is built in
    `kashier_manager.py`; `accounts.google.com` comes from the OAuth metadata
    URL. Neither appears in frontend source.
  * **Fetched at runtime by a third-party script** — GTM pulls
    `google-analytics.com`, Clarity beacons to `c.bing.com`, the Meta Pixel to
    `facebook.com`. Our source names none of them.
  * **Hardcoded in one page far from the feature** — `*.b-cdn.net` lives in a
    `<video src>` in `index.html` and a VSL URL in `chat.html`.

So: only `*.supabase.co` was removable, because it is the only one where the
calling code itself was deleted. For anything else, check the database and the
server-generated URLs before concluding an origin is unused — a CSP that blocks
something real is a broken page, and the breakage is silent.
