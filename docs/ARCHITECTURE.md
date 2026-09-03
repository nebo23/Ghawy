# Ghawy — Architecture Map (Phase 0 draft)

> **Status: draft.** Written in Phase 0 from a read-only survey of the tree and
> of the running production containers. It records the system *as it is today*,
> including the parts that are wrong. Phase 7 rewrites it as the final state.
>
> Measured 2026-09-03 on branch `claude/community-courses-improvements-6tto3e`.

---

## 1. What this is

A subscription learning platform: paid courses with video lessons, a members'
community (channels, threads, direct messages, live presence), live sessions,
exams, certificates, project submissions, and an admin/owner back office with
its own email-campaign engine.

Two payment rails (Kashier card checkout, and manual bank/Vodafone-Cash
receipts), Google sign-in alongside email/password, and a large amount of
transactional and lifecycle email.

**Stack.** FastAPI + SQLAlchemy + PostgreSQL 16 behind nginx, all in Docker
Compose. The frontend is vanilla HTML/CSS/JS — no build step, no framework, no
bundler. Pages are served as static files by nginx and talk to the API over
`fetch`.

## 2. Size

| | Files | Lines |
|---|---|---|
| Python (`backend/`) | 110 | 25,185 |
| JavaScript (`frontend/`, excl. vendor) | 30 | 23,181 |
| CSS (excl. vendor) | 14 | 27,461 |
| HTML pages | 31 | 33,375 |

241 HTTP/WS endpoints across 27 routers plus 5 defined directly on `main.py`.
50 tables in `models.py`; 52 in the production database.

Of the 33,375 HTML lines, **12,267 are inline `<script>`** — chat (3,120), DMs
(3,024), course detail (2,054) and the team dashboard (671) hold most of it.

## 3. Entrypoint — `backend/main.py`

```
main.py
 ├─ FastAPI(...)                        line 259
 ├─ SessionMiddleware                   line 274   (starlette, SECRET_KEY)
 ├─ CORSMiddleware                      line 275   (origins from env)
 ├─ Base.metadata.create_all(engine)    line 285   ⚠ at import time
 ├─ seed_defaults()                     line 286   ⚠ at import time
 ├─ mount /static                       line 305
 ├─ include_router × 27                 lines 308–334
 ├─ 5 endpoints defined inline          lines 336–387
 └─ @app.on_event("startup")            line 389   expand_threadpool
```

Two structural problems, both Phase 1 work:

* ~~`create_all()` and `seed_defaults()` run at import time~~ — **fixed in
  Phase 1.** Both now run inside the `lifespan` handler, and seeding takes a
  Postgres advisory lock so N workers cannot race.
* ~~`create_all()` is how half the schema actually exists~~ — **fixed in
  Phase 1.** It was worse than half: only **8** of the 50 tables were ever
  created by a migration. `ghawy_baseline` now creates all 50, and `create_all`
  is off the production path entirely. See §7.

The anyio threadpool is raised to 120 in that same `lifespan` handler; that is
the fix for the 2026-07-21 congestion collapse and must not be reverted
casually. It moved off `@app.on_event` in Phase 1 because FastAPI silently
ignores `on_event` once a `lifespan` is passed — leaving it there would have
disabled it with no error anywhere.

## 4. Routers

Prefix, responsibility, and the tables each one touches.

| Router | Prefix | Owns | Tables |
|---|---|---|---|
| `users` | `/auth` | register, login, email verification, password reset, token issue | users, payments |
| `google_auth` | `/auth` | Google OAuth login + handoff exchange | users, manual_payment_requests |
| `profile` | `/profile` | own profile, avatar, heartbeat/presence, subscription info, public profiles | users, payments, channels, messages, posts, phone_otps |
| `payment` | `/payment` | Kashier checkout create + success/fail redirects | payments, coupons, users |
| `webhooks` | `/webhooks` | Kashier server-to-server webhook | payments, users |
| `manual_payments` | `/manual-payments` | bank / Vodafone-Cash receipt rail, admin approve/reject | manual_payment_requests, payments, coupons, users |
| `coupons` | `/coupons` | coupon preview + redemption, admin CRUD | coupons, coupon_redemptions, payments, users |
| `courses` | `/courses` | catalogue, lessons, progress, playback OTP, reviews, certificates, admin course/lesson CRUD | courses, lessons, user_progress, lesson_playback_grants, certificates, course_reviews, users |
| `exams` | (mixed) | course exams and attempts, admin exam CRUD | exams, exam_attempts, courses, lessons, users |
| `projects` | (mixed) | project submissions and admin review | project_submissions, courses, users |
| `chat` | `/chat` | channels, messages, reactions, reads, DM list, online count | channels, chat_members, messages, message_reads, posts, post_channel_reads, users |
| `ws` | `/ws` | the community WebSocket | channels, chat_members, messages, users |
| `posts` | `/posts` | channel threads, comments, reactions, pins | posts, comments, post_likes, post_reactions, comment_reactions, categories, channels, notifications, users |
| `ai_updates` | `/ai-updates` | the AI Updates feed: posts, polls, reactions, comments | ai_update_* (7 tables), posts, comments, users |
| `notifications` | `/notifications` | notification list + mark read | notifications, users |
| `live` | (mixed) | live sessions, registration, attendees, a legacy WS | live_sessions, live_attendees, session_bookings, session_reminders, users |
| `guests` | `/guests` | guests of honour, their sessions, member suggestions | guests, guest_sessions, suggested_guests, users |
| `feedbacks` | `/feedbacks` | community feedback | feedbacks, users |
| `reports` | `/reports` | daily reports | daily_reports, users |
| `help_center` | `/help-center` | help centre | users |
| `atlas` | `/atlas` | the Atlas legacy-member free-month promo (OTP) | legacy_emails, users |
| `birthday` | `/birthday` | birthday gift claim → admin approval | birthday_gift_claims, channels, chat_members, messages, users |
| `files` | `/files` | authorized serving of uploaded files | (reads across many) |
| `admin` | `/admin` | the team dashboard: members, subscriptions, payments, staff permissions, roles, student progress | users, payments, courses, lessons, exams, exam_attempts, certificates, manual_payment_requests, live_sessions, admin_member_notes, user_progress |
| `email_campaigns` | `/admin/email-campaigns` | owner-only campaign composer and sender | email_campaign_sends, legacy_emails, payments, users |
| `dashboard` | `/dashboard` | the member dashboard summary | aggregates across courses, lessons, posts, exams, progress |
| `stats` | `/stats` | public site statistics (cached) | users |

## 5. Auth and authorization

**Tokens.** HS256 JWT, `SECRET_KEY` from env, **30-day expiry**
(`users.py:39`). Carried as `Authorization: Bearer`. A `token_version` claim
allows server-side invalidation.

**The dependency ladder** (`app/routers/users.py`):

| Dependency | Used by | Means |
|---|---|---|
| `get_current_user` | 72 endpoints | a valid token — a logged-in account |
| `get_current_active_member` | 87 endpoints | logged in **and** holds a live subscription |
| `get_current_admin_user` | 6 endpoints | `is_admin` |
| `require_perm(PERM_*)` | 43 endpoints | a specific staff permission |
| `get_current_user_optional` | 1 endpoint | logged in or not, both fine |

**Staff permissions** (`app/services/permissions.py`) are the real admin model:
the owner grants named permissions per admin, stored in `users.staff_permissions`,
and the team dashboard's tabs are keyed to the same strings. A "role" is a
preset bundle of those permissions plus a label. Owner-only paths check
`is_owner`.

**31 of the 241 endpoints declare no auth dependency at all.** Most are
public by design (login, register, the Kashier webhook, the Google callback,
the public catalogue and stats). They are listed and individually classified in
[`API-MAP.md`](API-MAP.md) — **Phase 3 confirms each one**; Phase 0 only records
them.

**WebSocket auth is not a dependency.** `ws.py:65` accepts the socket first and
then waits up to 10s for an auth message containing the token — deliberately, to
keep the token out of URLs and access logs. Authorization for posting is a
separate function, `_may_post_to_channel`, which must stay in agreement with
`chat.ensure_channel_access`; if the two ever disagree, the looser one is a
privacy hole.

## 6. Data model

50 tables. The clusters:

* **Identity / billing** — `users`, `payments`, `coupons`, `coupon_redemptions`,
  `manual_payment_requests`, `legacy_emails`, `phone_otps`
* **Learning** — `courses`, `lessons`, `user_progress`,
  `lesson_playback_grants`, `certificates`, `course_reviews`, `exams`,
  `exam_attempts`, `project_submissions`
* **Community** — `channels`, `chat_members`, `messages`,
  `chat_message_reactions`, `message_reads`, `posts`, `comments`, `post_likes`,
  `post_reactions`, `comment_reactions`, `post_channel_reads`, `categories`
* **AI Updates** — `ai_update_posts`, `ai_update_polls`,
  `ai_update_poll_options`, `ai_update_poll_votes`, `ai_update_reactions`,
  `ai_update_comments`, `ai_update_reads`
* **Events** — `live_sessions`, `live_attendees`, `session_bookings`,
  `session_reminders`, `session_projects`, `guests`, `guest_sessions`,
  `suggested_guests`
* **Ops** — `notifications`, `feedbacks`, `daily_reports`,
  `admin_member_notes`, `email_campaign_sends`, `birthday_gift_claims`

Two known dead spots, both recorded in [`FINDINGS.md`](FINDINGS.md):
`user_course_progress` is empty and nothing writes it (learners are derived from
`lesson_playback_grants ∪ user_progress`), and the production database carries a
`subscription_repair_2026_08_14` table that no model declares.

## 7. Migrations

Alembic, **49 revisions** in `backend/alembic/versions/`. One root
(`ghawy_baseline`), one head (`c9e1d3a7b542`), no missing parents. Production is
stamped at head.

```
$ alembic heads
c9e1d3a7b542 (head)
```

Reports of "3 heads and 2 roots" come from mis-parsing the tuple
`down_revision` of `4823c6c0b288_merge_multiple_heads.py`, which spans two
lines — that revision is a *merge*, not a second root. Ask alembic, do not grep.
The fork at `f1201efadb0f` (`9b2d6f5a8c31` / `e478012af2b4`) is closed by that
merge and always was.

### The defect that was real, and how it is closed

For most of the project's life the schema was built by
`Base.metadata.create_all()` at import time, not by Alembic. `--autogenerate`
was then usually run against a database `create_all` had *already* updated, so
six revisions came out completely empty and **only 8 of the 50 tables were ever
created by a migration**. `alembic upgrade head` on an empty database died at
the first ALTER against a table nothing had created:

```
sqlalchemy.exc.ProgrammingError: relation "comment_reactions" does not exist
[SQL: ALTER TABLE comment_reactions ADD UNIQUE (comment_id, user_id)]
```

Against production — which already had every table — it worked, which is why
this stayed invisible.

**`ghawy_baseline`** (`0000_ghawy_baseline_schema_snapshot.py`) is now the root
of the history and creates all 50 tables. It is a frozen snapshot, verified by
diffing `pg_dump --schema-only` of production against the schema a clean
`upgrade head` produces — every column, type, nullability, default, index and
foreign key matches. It is *not* regenerated from the models; later schema
changes go in later revisions as normal.

The 42 pre-baseline revisions that do real work each open with:

```python
if baseline_created_schema():
    return
```

`baseline_created_schema()` (`backend/migration_utils.py`) is true only when the
`ghawy_schema_baseline` marker table exists, and only the baseline writes it —
and only when it genuinely created the schema itself. So:

| Database | Baseline | The 42 historical revisions |
|---|---|---|
| Empty | creates 50 tables, writes marker | skip — snapshot already has their change |
| Production / a dump of it | already an ancestor, never runs | run for real if pending |
| Has tables but never stamped | no-ops, **writes no marker** | run for real |

Verified in all three directions: clean → head produces production's schema; a
full production clone upgrades as a no-op with all 52 row counts unchanged; a
clone rewound one revision really re-applies it.

### Schema creation is no longer on the import path

`Base.metadata.create_all()` and `seed_defaults()` used to run at module import
in `backend/main.py`, i.e. once per Gunicorn worker, before the app object
existed. They now live in a `lifespan` handler (alongside the anyio threadpool
bump and the APScheduler start/stop, which moved off `@app.on_event` so FastAPI
does not silently drop them). `create_all` is gone from the production path: if
the schema is missing the app refuses to start and names the fix, unless
`DEV_CREATE_ALL=1` is set outside production. Seeding takes a Postgres advisory
lock so N workers cannot race each other into the same INSERT.

Migrations run on container start, before Gunicorn:

```yaml
command: sh -c "alembic upgrade head && gunicorn main:app --config gunicorn.conf.py"
```

## 8. Payments

* **Kashier (card).** `POST /payment/kashier/create` builds the checkout;
  the browser returns to `/payment/kashier/success|fail`; the authoritative
  event is `POST /webhooks/kashier`. Prices are resolved server-side from
  `PLAN_PRICES` — never from the client. Redirect signature is the raw
  `signature` query param; webhook signature is `x-kashier-signature`
  (sorted keys, RFC3986, API key). The body's `hash` field is unusable.
* **Manual rail.** Bank transfer and Vodafone Cash share `/pay` via `?method=`;
  members upload a receipt, admins approve or reject. Receipts are magic-byte
  checked on upload.
* **Coupons** are row-locked on redemption to stop concurrent double-spend.

## 9. Uploads and file serving

`app/routers/files.py` splits categories in two:

* `PUBLIC_CATEGORIES = {avatars, course-thumbnails, posts}` — served to anyone.
* Everything else is **protected**: the backend authorizes the request, then
  hands the file to nginx via `X-Accel-Redirect` into the internal
  `^~ /_protected_uploads/` location (`X_ACCEL_UPLOADS_PREFIX`). With that env
  var unset the backend streams the bytes itself — the local-dev path.

Protected files live under `/files/<category>/`; nginx deliberately 404s
`/api/uploads/<protected>/`. Real upload bytes live in the `ghawy_uploads_data`
Docker volume — `backend/uploads/` in the tree is stale.

`courses._uploads_path_for` is the reference implementation of safe path
resolution (it refuses traversal); Phase 3 confirms every serving path uses
equivalent validation.

## 10. Realtime

One WebSocket at `/ws` (`ws.py`) backed by `services/ws_manager.py`, plus a
legacy live-session socket at `/api/live-sessions/ws`. Hard-won constraints:

* WS handlers must use **short-lived DB sessions** — holding one across an await
  pinned the pool and caused an outage.
* **Every `ws.send` needs a timeout** — a stalled socket otherwise pins its
  session; recreating nginx reliably produces stalled sockets.
* Presence is broadcast carefully: a per-channel fan-out with a refetch per
  event was the cause of the "DM list polling storm".

## 11. Background jobs

APScheduler (`app/scheduler.py`), all cron, all Africa/Cairo-relevant:

| Time | Job | Does |
|---|---|---|
| 09:00 | `daily_subscription_check_job` | deactivates expired subscriptions |
| 09:00 | `renewal_reminder` | renewal reminder mail |
| 09:15 | `expiry_5day_reminder` | 5-days-left mail |
| 09:30 | `birthday_email` | birthday gift offer |
| 09:45 | `inactive_6day` | nudge for members idle 6+ days |
| (interval) | `send_winback_emails` | one-time "ليه وقفت؟" 24h after an unpaid signup |

Two rules learned the hard way: worker restarts every ~8 minutes
(`max_requests`) reset interval timers, so any job with a period over ~5 minutes
needs an explicit `next_run_time` near boot; and **no synchronous SMTP or DB work
may run on the event loop** — that froze the whole site once. Jobs go through
`to_thread`, mail goes out on background threads.

## 12. Email

`app/services/email_service.py` (88 KB) is the whole transactional and lifecycle
surface; `email_campaign_service.py` is the owner-facing campaign engine, with
campaigns persisted as JSON in the `campaigns_data` volume.

Everything renders through one shared base, `render_ghawy_email` — light theme,
black logo box, lime CTA, blue footer links, `FROM_NAME` "Ghawy Team". **Editing
that base restyles every lifecycle email at once.** Template variables genuinely
arabize names, governorates and countries (`{first_name_ar}`, `{greeting}`,
`{governorate_ar}`).

Gmail SMTP chokes after roughly 80 rapid sends.

## 13. Frontend

No build step. `frontend/*.html` are served directly; shared behaviour lives in
`frontend/src/js/`.

The load-bearing shared modules:

| Module | Loaded by | Responsibility |
|---|---|---|
| `utils.js` | 26 pages | `API` base, auth header, `showToast`, `escapeHtml`, `setTheme`, `bidiDir`, `formatChatText`, the global 30s notification poll |
| `i18n.js` | 26 pages | translation for the public/marketing pages |
| `community-i18n.js` | 11 pages | translates the whole community + RTL when `ar` is preferred |
| `dashboard-new.js` | 12 pages | member shell: sidebar, badges, online count, chat widget |
| `whats-new.js` | 11 pages | once-per-version popup |
| `layout.js` | 7 pages | nav / drawer / footer for the public marketing site |
| `catalog-data.js` + `catalog.js` | 7 / 5 pages | course catalogue facts, then renderers |
| `course-card.js` | 2 pages | the single course card used by dashboard and catalogue |

Conventions that must be preserved (captured properly in Phase 7's `CLAUDE.md`):
read the language only via `window.currentLang()`; `data-ar` wipes children so
icon buttons use `data-ar-aria`; the `ghawy_lang` migration must exist in *both*
`i18n.js` and `community-i18n.js` because 6 pages skip `i18n.js`; user-supplied
names reach `innerHTML` on every page, so `escapeHtml` is mandatory; JS edits
need the `?v=` cache-bust bumped or nginx serves the old file for 7 days.

## 14. Docker, nginx, deployment

Three containers (`docker-compose.prod.yml`):

* `ghawy_postgres` — Postgres 16, published on **`127.0.0.1:5432` only**,
  on the `internal` network.
* `ghawy_backend` — the FastAPI image, `alembic upgrade head` then Gunicorn +
  UvicornWorkers. Volumes: `uploads_data`, `static_data`, `campaigns_data`.
* `ghawy_nginx` — TLS termination, static file serving, API proxy.

nginx config lives in `nginx/` (`nginx.conf`, `conf.d/api_proxy.conf`,
`conf.d/proxy_params.conf`, `conf.d/security_headers.conf`). Behaviours to know:
`.html` is stripped with a 301, http redirects to https, assets are cached 7
days, `/api/uploads` is served by nginx directly, and API rate limits use exact
`^~ /api/` matching because a regex location would win over it.

**Deployment asymmetry — the single most important operational fact:**

* the **frontend is bind-mounted**, so an edit is live immediately;
* the **backend is baked into the image**, so it needs a rebuild and restart,
  and migrations run on startup.

nginx config changes need `--force-recreate` (the bind mount is by inode).
Restarting the backend can saturate the DB pool through thundering-herd polling
and WebSocket reconnects.

## 15. Tests

There is effectively no automated test coverage.

* `backend/tests/test_email_and_names.py` — the only genuine test. Pure unit
  tests over the signup guards and name splitting. Safe anywhere. 6 pass.
* `backend/scripts/acceptance_*.py` — three end-to-end acceptance **scripts**
  (security, Atlas promo + reset, team roles). Each rebuilds the schema and
  drives the real app. They are destructive by design; see
  `backend/scripts/README.md`. Phase 0 moved them out of `tests/` and put a
  guard in front of them.

"The tests passed" is not evidence that nothing broke. The acceptance gates in
each phase are.
