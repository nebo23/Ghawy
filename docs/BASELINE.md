# Ghawy — Behavioural Baseline (Phase 0)

The reference for judging "did I break something" in every later phase.
Captured 2026-09-03 on branch `claude/community-courses-improvements-6tto3e`.

---

## 0. How this was captured, and what it does not contain

**This host is production.** `/opt/ghawy` is the deployed tree; the three
production containers were up and serving real users throughout. Standing up a
second local instance was not attempted: `backend/.env` resolution and the
Postgres port published on `127.0.0.1:5432` both point at the live database, and
a mistake there costs real data.

So the baseline was taken **against the running production instance, read-only**
— `GET` requests over `https://localhost` with a `Host: ghawy.ai` header, plus
`docker logs` and one read-only `SELECT`. No writes, no authenticated mutations,
no test accounts created.

**What is therefore missing, and must not be pretended otherwise:**

* **No screenshots.** No browser binary is installed on this host
  (`google-chrome`, `chromium` all absent), and installing one on a production
  host was not a Phase 0 decision to make unilaterally.
* **No browser console errors.** Same reason. Any later claim of "no new console
  errors" must be earned with a real browser, not inferred from this file.
* **No authenticated page behaviour.** Every measurement below is the anonymous
  HTML shell. What a logged-in member's dashboard renders is not captured.

These three gaps are real limitations of this baseline. Where a later acceptance
gate depends on them, the gate needs a browser — see
[`FINDINGS.md`](FINDINGS.md).

---

## 1. Application boots

The backend's own startup log for the current run:

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade b3d7e91c2a45 -> c9e1d3a7b542, add team_role to users
```

Migrations ran and applied cleanly on boot. Containers:

| Container | Image | State |
|---|---|---|
| `ghawy_backend` | `ghawy-backend` | Up, healthy |
| `ghawy_postgres` | `postgres:16-alpine` | Up, healthy |
| `ghawy_nginx` | `nginx:1.27-alpine` | Up |

Database: 52 tables, `alembic_version` = `c9e1d3a7b542`, which equals
`alembic heads`.

`GET /api/` → `200 {"message":"Community API Is Working"}`

## 2. All 31 pages serve

Every page returns **200**. Times are nginx-local (no network, no rendering) —
useful as a regression tripwire on payload size, not as a user-experience metric.

| Page | Status | Bytes | `<script src>` | stylesheets |
|---|---:|---:|---:|---:|
| `/` (index) | 200 | 118,434 | 11 | 3 |
| `/chat` | 200 | **254,822** | 7 | 4 |
| `/direct-messages` | 200 | **249,583** | 7 | 4 |
| `/course-detail` | 200 | **214,352** | 8 | 3 |
| `/teamdashboard` | 200 | **175,591** | 7 | 3 |
| `/profile-settings` | 200 | 47,142 | 8 | 3 |
| `/terms` | 200 | 41,767 | 2 | 2 |
| `/privacy` | 200 | 39,353 | 2 | 2 |
| `/guest-of-honors` | 200 | 36,508 | 8 | 4 |
| `/help-center` | 200 | 34,340 | 6 | 4 |
| `/ai-updates` | 200 | 33,328 | 8 | 4 |
| `/tracks` | 200 | 31,259 | 6 | 2 |
| `/profile` | 200 | 31,122 | 8 | 3 |
| `/atlas` | 200 | 28,593 | 2 | 2 |
| `/dashboard` | 200 | 27,060 | 9 | 3 |
| `/course-details` | 200 | 24,135 | 6 | 2 |
| `/dashboard-courses` | 200 | 24,057 | 10 | 3 |
| `/build-with-me` | 200 | 23,969 | 8 | 4 |
| `/admin-course-detail` | 200 | 19,792 | 5 | 4 |
| `/onboarding` | 200 | 19,778 | 5 | 1 |
| `/pay` | 200 | 18,084 | 6 | 3 |
| `/register` | 200 | 17,345 | 7 | 1 |
| `/renewal` | 200 | 17,121 | 3 | 4 |
| `/instructors` | 200 | 15,648 | 6 | 2 |
| `/reviews` | 200 | 13,017 | 5 | 2 |
| `/pricing` | 200 | 12,289 | 6 | 2 |
| `/reset-password` | 200 | 10,494 | 5 | 1 |
| `/login` | 200 | 9,687 | 5 | 1 |
| `/courses` | 200 | 7,700 | 6 | 2 |
| `/verify-email` | 200 | 5,247 | 5 | 1 |
| `/auth-complete` | 200 | 3,887 | 0 | 0 |

**All 44 distinct local assets referenced across those pages return 200.** Zero
404s. This is the exact check Phase 5 must re-run after any deletion.

Note `/admin-course-detail` serves normally despite being linked from nowhere.

## 3. Live traffic profile

7 hours of production logs, 157,419 requests:

| Endpoint | Requests |
|---|---:|
| `POST /profile/heartbeat` | 39,802 |
| `GET /chat/dm/list` | 23,536 |
| `GET /notifications/` | 19,606 |
| `GET /chat/community/unread` | 19,584 |
| `GET /ai-updates/unread` | 19,565 |
| `GET /chat/online-count` | 6,951 |
| `GET /profile/me` | 5,732 |
| `GET /chat/messages` | 3,631 |
| `GET /dashboard/summary` | 2,290 |
| `GET /` | 2,144 |
| `GET /chat/admins` | 1,582 |
| `POST /profile/offline` | 1,574 |
| `PUT /chat/community/read` | 1,115 |
| `PUT /chat/dm/read` | 978 |
| `GET /courses` | 840 |

**Polling share: 82.0%** (129,084 / 157,419).

Phase 4 is measured against this table. A drop in these counts is only a win if
§2 still serves and the badges, presence and DM counts still update.

## 4. Errors that already exist

These are the **pre-existing** errors. Anything not on this list, appearing
later, is a regression.

| Count | Message | Reading |
|---:|---|---|
| 56 | `WARNING app.routers.ws: WS auth failed: no/invalid auth message` — with close codes `1006`, `1001`, and empty | normal client disconnects racing the 10s auth window; noise, not a fault |
| 4 | `ERROR app.services.vdocipher: VdoCipher OTP generation failed for video d. Status: 400, Body: {"message":"Invalid videoId found"}` | **a real pre-existing bug** — a lesson holds the literal `vdo_video_id` "d". Logged in `FINDINGS.md`; out of Phase 0 scope |
| 1 | `[WARNING] Maximum request limit of 109158 exceeded. Terminating process.` | Gunicorn `max_requests` worker recycle; expected, and the reason interval scheduler jobs need an explicit `next_run_time` |
| 1 | `WARNING app.services.otp_manager: ❌ OTP مش صح أو انتهت صلاحيته` | a user mistyped an OTP |

No tracebacks, no unhandled exceptions, no database errors in the window.

## 5. Tests, as they actually stand

```
$ python3 backend/tests/test_email_and_names.py
  ok  test_compose_full_name
  ok  test_disposable_domains_blocked
  ok  test_fake_local_parts_blocked
  ok  test_real_emails_pass
  ok  test_split_compose_roundtrip
  ok  test_split_full_name
6 test functions passed
```

That is the entire safe automated coverage of a payments-handling production
application: six assertions over email filtering and name splitting.

The three acceptance scripts were **not run**. Running one requires a scratch
Postgres database, and creating one alongside the production database on this
host is a Phase 1 decision, not a Phase 0 one. Their guard was verified
separately — see §6.

## 6. The Phase 0 guard, verified

`backend/scripts/_acceptance_guard.py` refuses every unsafe target:

| `DATABASE_URL` | `ACCEPTANCE_DESTROY_DB` | Result |
|---|---|---|
| `…@localhost:5432/ghawy_db` | — | **exit 2** — "the database name configured for production" |
| `…@postgres:5432/ghawy_db` | — | **exit 2** — same |
| `…@localhost:5432/customer_data` | — | **exit 2** — "does not identify it as a throwaway" |
| unset | — | **exit 2** — "DATABASE_URL is not set" |
| `…@localhost:5432` (no db) | — | **exit 2** — "names no database" |
| `…/customer_data` | `other_db` | **exit 2** — override does not match target |
| `…/ghawy_db` | `ghawy_db` | **exit 2** — production refused even with the override |
| `…/ghawy_test`, `/scratch_db`, `/test_ghawy`, `/ghawy_scratch`, `/tmp_db` | — | approved, target printed |

The host-based check the brief suggested was deliberately **not** used:
production is published on `127.0.0.1:5432` here, so "localhost" would have
approved the production database.

## 7. What a later phase must re-check against this file

1. All 31 pages return 200 and all 44 assets return 200 (§2).
2. No error appears in `docker logs ghawy_backend` that is not in §4.
3. `alembic current` equals `alembic heads` and the app boots (§1).
4. Request counts moved in the intended direction and nothing else appeared (§3).
5. Authenticated behaviour — login, member dashboard, chat send/receive,
   upload, admin — **is not covered here** and needs a browser and a test
   account before Phase 3 or Phase 6 can honestly claim it.
