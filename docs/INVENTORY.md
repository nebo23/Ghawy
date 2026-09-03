# Ghawy — File Inventory (Phase 0)

Every file under `frontend/src/js`, `frontend/src/css`, `frontend/*.html` and
`backend/app/**`, classified with the evidence for the classification.

Measured 2026-09-03.

## Classifications

| Label | Meaning |
|---|---|
| `REQUIRED` | the application cannot start or serve without it |
| `USED` | referenced and reached on a normal path |
| `UNUSED` | verified unreferenced — every check below came back empty |
| `DUPLICATE` | a second copy of something that already exists elsewhere |
| `LEGACY` | superseded, still reachable |
| `DEV-ONLY` | development or operations tooling, not a runtime path |
| `TEST-ONLY` | test or acceptance code |
| `UNKNOWN` | **not established** — must be investigated before anything is done to it |

**Rule 5 applies to this whole document.** Nothing here authorises a deletion.
`UNUSED` records that the searches came back empty; the decision, and the
re-verification that precedes it, happen in Phase 5.

Verification performed for each entry: full-repo text search · `<script>` and
`<link>` references in all 31 HTML pages · dynamic `import()` · backend imports ·
`docker-compose.prod.yml` and `backend/Dockerfile` · `deploy.sh` · `nginx/` ·
`backend/tests/` and `backend/scripts/` · `app/scheduler.py` · router
registration in `main.py` · documentation · a live HTTP fetch against the
running production instance.

---

## 1. Backend — `backend/app/`

### Top-level

| File | Size | Classification | Evidence |
|---|---:|---|---|
| `database.py` | 1.5 KB | `REQUIRED` | engine + `SessionLocal` + `get_db`; imported everywhere |
| `models.py` | 60 KB | `REQUIRED` | 50 tables; `Base` drives `create_all` |
| `schemas.py` | 20 KB | `REQUIRED` | Pydantic request/response models |
| `scheduler.py` | 17 KB | `REQUIRED` | 6 cron jobs; imported at startup |
| `__init__.py` | 0 B | `REQUIRED` | package marker |

### Routers — all 27 `USED`

Every router in `app/routers/` is registered in `main.py` (lines 308–334) and
serves at least one endpoint. Responsibilities and the tables each touches are
in [`ARCHITECTURE.md` §4](ARCHITECTURE.md). None is a deletion candidate.

One note carried to Phase 3, not a classification: `live.py` contains
`get_live_sessions_legacy` (`GET /api/live-sessions`) and a second WebSocket at
`/api/live-sessions/ws`, both named "legacy" in the source while the current
live feature is served elsewhere in the same router. That makes them `UNKNOWN`,
not `LEGACY` — "legacy" in a function name is the author's label, not evidence
that nothing calls it.

### Services — all 22 `USED`

Every module in `app/services/` is imported by at least one router, service or
the scheduler. Reference counts:

| Module | Imports | Module | Imports |
|---|---:|---|---:|
| `email_service.py` (88 KB) | 15 | `file_service.py` | 5 |
| `permissions.py` | 11 | `subscription_service.py` | 5 |
| `progress_service.py` | 10 | `kashier_manager.py` | 3 |
| `ws_manager.py` | 9 | `disposable_emails.py` | 3 |
| `name_utils.py` | 7 | `payment_service.py` | 3 |
| `bunny_stream.py` | 4 | `attachments.py`, `chat_reactions.py`, `email_campaign_service.py`, `mentions_service.py`, `vdocipher.py` | 2 |
| `coupon_service.py` | 4 | `campaign_store.py`, `invoice_pdf.py`, `live_manager.py`, `otp_manager.py`, `turnstile.py` | 1 |

The single-reference modules are all genuinely reached: `turnstile` from
registration, `invoice_pdf` from payments, `campaign_store` from the campaign
router, `otp_manager` from the Atlas promo, `live_manager` from live sessions.

`permissions.py` carries comments recording decisions made with the client.
Those are documentation and are not to be stripped as clutter.

### Backend, outside `app/`

| File | Classification | Evidence |
|---|---|---|
| `main.py` | `REQUIRED` | entrypoint; `gunicorn main:app` |
| `gunicorn.conf.py` | `REQUIRED` | named in the compose `command` |
| `alembic/env.py`, `alembic.ini` | `REQUIRED` | `alembic upgrade head` runs on every boot |
| `alembic/versions/*.py` (48) | `REQUIRED` | migration history; **none may be deleted** |
| `tests/test_email_and_names.py` | `TEST-ONLY` | the one safe test; 6 pass |
| `scripts/acceptance_*.py` (3) | `TEST-ONLY`, destructive | see `backend/scripts/README.md` |
| `scripts/_acceptance_guard.py` | `TEST-ONLY` | added in Phase 0 |
| `.env.production` | `REQUIRED` | `env_file` in compose |
| `.env.production.bak.1783362291` | `UNKNOWN` | a dated backup of secrets sitting in the tree; not referenced, but deleting a secrets file is the owner's call |
| `uploads/` | `LEGACY` | real uploads live in the `ghawy_uploads_data` volume; this copy is stale |
| `campaigns/` | `REQUIRED` | mount point for `campaigns_data` |
| `static/` | `REQUIRED` | mounted at `/static` |

---

## 2. Frontend

### `frontend/src/js/` — 29 files

| File | Size | Classification | Loaded by |
|---|---:|---|---|
| `admin-courses.js` | 14,690 B | `USED` | 1 page(s): admin-course-detail.html |
| `ai-updates.js` | 72,332 B | `USED` | 1 page(s): ai-updates.html |
| `bwm.js` | 13,993 B | `USED` | 1 page(s): build-with-me.html |
| `catalog-data.js` | 37,000 B | `USED` | 7 page(s): course-details.html, courses.html, dashboard-courses.html, dashboard.html… |
| `catalog.js` | 53,862 B | `USED` | 5 page(s): course-details.html, courses.html, index.html, instructors.html… |
| `community-i18n.js` | 55,813 B | `USED` | 11 page(s): ai-updates.html, build-with-me.html, chat.html, course-detail.html… |
| `course-card.js` | 12,693 B | `USED` | 2 page(s): dashboard-courses.html, dashboard.html |
| `courses.js` | 36,947 B | `USED` | 1 page(s): dashboard-courses.html |
| `dashboard-new.js` | 47,992 B | `USED` | 12 page(s): admin-course-detail.html, ai-updates.html, build-with-me.html, chat.html… |
| `dashboard.js` | 18,152 B | `UNUSED` | **no page loads it; zero references repo-wide** |
| `faq.js` | 11,293 B | `USED` | 2 page(s): index.html, pricing.html |
| `goh.js` | 18,859 B | `USED` | 1 page(s): guest-of-honors.html |
| `i18n.js` | 31,338 B | `USED` | 26 page(s): ai-updates.html, build-with-me.html, chat.html, course-detail.html… |
| `layout.js` | 22,634 B | `USED` | 7 page(s): course-details.html, courses.html, index.html, instructors.html… |
| `login.js` | 4,967 B | `USED` | 1 page(s): login.html |
| `main.js` | 42,796 B | `USED` | 1 page(s): index.html |
| `onboarding.js` | 21,742 B | `USED` | 1 page(s): onboarding.html |
| `pay.js` | 32,762 B | `USED` | 1 page(s): pay.html |
| `pricing.js` | 47,842 B | `USED` | 3 page(s): index.html, pay.html, pricing.html |
| `profile.js` | 23,613 B | `USED` | 2 page(s): profile-settings.html, profile.html |
| `recorder.js` | 3,803 B | `UNUSED` | **no page loads it; zero references repo-wide** |
| `register.js` | 13,932 B | `USED` | 1 page(s): register.html |
| `renewal.js` | 27,516 B | `USED` | 1 page(s): renewal.html |
| `reset-password.js` | 8,448 B | `USED` | 1 page(s): reset-password.html |
| `reviews.js` | 39,517 B | `USED` | 2 page(s): index.html, reviews.html |
| `team.js` | 268,883 B | `USED` | 1 page(s): teamdashboard.html |
| `utils.js` | 37,643 B | `USED` | 26 page(s): admin-course-detail.html, ai-updates.html, atlas.html, build-with-me.html… |
| `verify-email.js` | 4,262 B | `USED` | 1 page(s): verify-email.html |
| `whats-new.js` | 16,521 B | `USED` | 11 page(s): ai-updates.html, build-with-me.html, chat.html, course-detail.html… |

### `frontend/src/css/` — 14 files

| File | Size | Classification | Loaded by |
|---|---:|---|---|
| `admin-courses.css` | 13,753 B | `USED` | 1 page(s): admin-course-detail.html |
| `ai-updates.css` | 42,118 B | `USED` | 1 page(s): ai-updates.html |
| `bwm.css` | 12,723 B | `USED` | 1 page(s): build-with-me.html |
| `community.css` | 42,696 B | `USED` | 2 page(s): chat.html, direct-messages.html |
| `dashboard-new.css` | 70,145 B | `USED` | 13 page(s): admin-course-detail.html, ai-updates.html, build-with-me.html, chat.html… |
| `dashboard.css` | 74,656 B | `USED` | 14 page(s): admin-course-detail.html, ai-updates.html, build-with-me.html, chat.html… |
| `goh.css` | 17,972 B | `USED` | 1 page(s): guest-of-honors.html |
| `help-center.css` | 4,451 B | `USED` | 1 page(s): help-center.html |
| `main.css` | 232,361 B | `USED` | 8 page(s): course-details.html, courses.html, index.html, instructors.html… |
| `onboarding.css` | 16,032 B | `USED` | 1 page(s): onboarding.html |
| `pay.css` | 19,485 B | `USED` | 1 page(s): pay.html |
| `renewal.css` | 13,994 B | `USED` | 1 page(s): renewal.html |
| `style.css` | 12,851 B | `USED` | 4 page(s): atlas.html, login.html, reset-password.html, verify-email.html |
| `team.css` | 67,682 B | `USED` | 1 page(s): teamdashboard.html |

### `frontend/*.html` — 31 pages

| Page | Lines | Inline JS | Classification | Notes |
|---|---:|---:|---|---|
| `chat.html` | 6,013 | 3,120 | `USED` |  |
| `direct-messages.html` | 5,972 | 3,024 | `USED` |  |
| `course-detail.html` | 5,012 | 2,054 | `USED` |  |
| `teamdashboard.html` | 3,684 | 671 | `USED` |  |
| `index.html` | 1,899 | 479 | `USED` |  |
| `profile-settings.html` | 877 | 252 | `USED` |  |
| `atlas.html` | 863 | 288 | `USED` |  |
| `help-center.html` | 674 | 352 | `USED` |  |
| `guest-of-honors.html` | 642 | 83 | `USED` |  |
| `ai-updates.html` | 598 | 52 | `USED` |  |
| `profile.html` | 567 | 82 | `USED` |  |
| `privacy.html` | 532 | 46 | `USED` |  |
| `tracks.html` | 531 | 431 | `USED` |  |
| `dashboard.html` | 520 | 85 | `USED` |  |
| `terms.html` | 506 | 46 | `USED` |  |
| `course-details.html` | 462 | 319 | `USED` |  |
| `build-with-me.html` | 456 | 120 | `USED` |  |
| `register.html` | 429 | 50 | `USED` |  |
| `dashboard-courses.html` | 428 | 70 | `USED` |  |
| `admin-course-detail.html` | 381 | 46 | `UNKNOWN` | **zero references repo-wide**; sole loader of `admin-courses.js`/`.css`; serves 200 |
| `pay.html` | 361 | 34 | `USED` |  |
| `instructors.html` | 298 | 204 | `USED` |  |
| `renewal.html` | 297 | 32 | `USED` |  |
| `onboarding.html` | 288 | 34 | `USED` |  |
| `reviews.html` | 236 | 71 | `USED` |  |
| `pricing.html` | 201 | 32 | `USED` |  |
| `reset-password.html` | 184 | 43 | `USED` |  |
| `login.html` | 179 | 48 | `USED` |  |
| `courses.html` | 138 | 32 | `USED` |  |
| `verify-email.html` | 111 | 34 | `USED` |  |
| `auth-complete.html` | 86 | 33 | `USED` |  |

### The two unreferenced JS modules

`dashboard.js` (18 KB) and `recorder.js` (3.8 KB) are classified `UNUSED`. The
searches that came back empty, for both:

* no `<script src>` on any of the 31 pages
* no occurrence of the filename anywhere in `frontend/`, `backend/`, `nginx/`,
  `scripts/`, `deploy.sh`, or `docker-compose.prod.yml`
* no dynamic `import()` and no string-built script tag
* fetched over HTTP: served (nginx serves the directory), but by nobody

Corroborating detail rather than proof: `dashboard.js` holds a fourth copy of
`fetchOnlineCount` and a `GET /dashboard/summary` call that `profile.js` also
makes, i.e. it reads as a superseded predecessor of `dashboard-new.js`.
`recorder.js` is a voice-recorder timer, and the known history of the voice-note
work records that `recorder.js` is dead code — the live recorder is elsewhere.

Phase 5 re-verifies both before removing either.

### `admin-course-detail.html` — `UNKNOWN`, do not touch

* zero references in the entire repository — no link, no redirect, no nginx rule
* it is nonetheless **served, and returns HTTP 200** with all assets resolving
* it is the **only** loader of `admin-courses.js` and `admin-courses.css`, so the
  three form an isolated island reachable only by typing the URL
* `admin-courses.js` polls `GET /courses/admin/lessons/{id}/status` every 3s,
  which is real, working video-transcode plumbing

An admin bookmark is a completely ordinary way for a page like this to be
reached, and nothing in the repository can rule it out. It stays `UNKNOWN`.
Phase 5 must answer "what opens it?" — and the only place that answer exists is
with the owner.

### Vendor

| Path | Size | Classification | Evidence |
|---|---:|---|---|
| `src/vendor/fontawesome/6.5.0/` | ~750 KB | `USED` | 18 pages |
| `src/vendor/fontawesome/7.0.0/` | ~750 KB | `DUPLICATE` | 6 pages; two majors of one icon font shipped side by side |
| `src/vendor/lucide/` | 412 KB | `USED` | 20 pages |

Icon libraries are self-hosted on purpose — icons vanishing has previously been
a CDN-dependency failure, so a CDN dependency is the first thing to check and
the last thing to reintroduce. Standardising on one FontAwesome major is Phase 5
and needs a visual check per page, because 6→7 renames glyphs.

Three pages (`register.html`, `privacy.html`, `terms.html`) still load
`cdn.tailwindcss.com`, and `index.html` loads `cdn.plyr.io` — recorded in
[`FINDINGS.md`](FINDINGS.md).

---

## 3. Repository root

| File | Classification | Evidence |
|---|---|---|
| `docker-compose.prod.yml` | `REQUIRED` | the production topology |
| `docker-compose.test.yml` | `UNKNOWN` | 165 bytes, referenced by nothing |
| `backend/docker-compose.yml` | `UNKNOWN` | a second compose file; not the one deployed |
| `deploy.sh` | `REQUIRED` | the deployment path |
| `nginx/` | `REQUIRED` | bind-mounted into `ghawy_nginx` |
| `scripts/backup.sh` | `DEV-ONLY` | operations |
| `scripts/migrate_upload_urls.py` | `DEV-ONLY` | must be re-run after any restore |
| `security/` | `REQUIRED` | the persistent IP blocklist + systemd unit |
| `ssl/` | `REQUIRED` | certificates |
| `backups/` | `DEV-ONLY` | not application code |
| `Requirements.txt` | `LEGACY` | see below |
| `AUDIT_REPORT.md` | `LEGACY` | stale; corrected in Phase 0 |
| `SERVER_SETUP.md` | `USED` | setup notes |
| `.vscode/`, `.claude/` | `DEV-ONLY` | editor / agent config |

### Root `Requirements.txt` — `LEGACY`, and not what it was reported as

It was reported as a stale duplicate of `backend/requirements.txt`. It is not a
duplicate — it is a **divergent stale fork**:

* 15 lines against the backend's 61
* it is **missing 12 packages the application actually needs**, including
  `apscheduler`, `gunicorn`, `authlib`, `pillow`, `weasyprint`, `boto3`,
  `requests`, `starlette`, `tzdata`, `email-validator`, `itsdangerous`
* it uniquely lists `sqlalchemy-utils` and `websocket-client`, which the backend
  does not install
* nothing installs from it: `backend/Dockerfile:13` copies `requirements.txt`
  from a build context of `./backend`, so it resolves to the backend file

Nothing builds from it and nothing can, since installing it would produce an
application that cannot start. Removal is Phase 5.
