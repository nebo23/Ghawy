# Ghawy — API Map (Phase 0)

Every backend endpoint, what calls it, and what is worth changing about it.
Measured 2026-09-03. **241 endpoints** across 27 routers plus `main.py`.

> **How to read the "Frontend caller" column.** It was produced by statically
> scanning every `fetch(...)` in `frontend/*.html` and `frontend/src/js/*.js`
> and normalising template literals. 128 endpoints matched a call site;
> **113 did not**.
>
> _None found_ means **the scanner did not find one** — it does **not** mean the
> endpoint is unused. Paths assembled at runtime, called from an admin tool, hit
> by an email link, or requested by an external service all read as "none".
> Under Rule 5 every one of these is `UNKNOWN` until individually investigated.
> Nothing in this document authorises a deletion.

---

## 1. Live traffic mix — the headline number

Taken from 7 hours of the running production backend (157,419 logged requests):

| Endpoint | Requests | Share |
|---|---:|---:|
| `POST /profile/heartbeat` | 39,802 | 25.3% |
| `GET /chat/dm/list` | 23,536 | 15.0% |
| `GET /notifications/` | 19,606 | 12.5% |
| `GET /chat/community/unread` | 19,584 | 12.4% |
| `GET /ai-updates/unread` | 19,565 | 12.4% |
| `GET /chat/online-count` | 6,951 | 4.4% |
| `GET /profile/me` | 5,732 | 3.6% |
| `GET /chat/messages` | 3,631 | 2.3% |
| `GET /dashboard/summary` | 2,290 | 1.5% |
| everything else | ~16,700 | 10.6% |

> **82.0% of all backend traffic is polling** — 129,084 of 157,419 requests.

Six endpoints produce four fifths of the load, and every one of them is a timer
in `utils.js` or `dashboard-new.js` rather than a user action. This is the
primary Phase 4 target. It is *not* a correctness problem — each of those
requests renders something real (a badge, a presence dot, a DM count) — so the
question is cadence and consolidation, not removal.

## 2. Polling inventory

| Where | Interval | Requests per tick | Notes |
|---|---|---|---|
| `utils.js:406` | 30s × 26 pages | `/notifications/`, plus the badge fetches | the single largest source of load |
| `dashboard-new.js:1057` | 30s × 12 pages | `/chat/online-count` | already `document.hidden`-gated |
| `chat.html:4498-4499` | 30s | `/chat/online-count`, `/chat/dm/list` | duplicated verbatim in DMs |
| `direct-messages.html:4522-4523` | 30s | same two | the other copy |
| `team.js:6157` | **4s** | team dashboard tick | admin-only, few sessions, but very hot |
| `admin-courses.js:235` | 3s | `/courses/admin/lessons/{id}/status` | video transcode poll; stops when ready |
| `main.js:233` | **5s** | *third party* — see below | public landing page |
| `main.js:282` | **10s** | *third party* — see below | public landing page |

### The landing-page polls do not touch this backend

`checkPurchases` (`main.js:136`) and `fetchLastPurchase` (`main.js:253`) both
poll **an external Supabase project**, `opetjxxzbmqzmqouqare.supabase.co`, with
a publishable API key hardcoded in the JavaScript. They drive the "someone just
bought" social-proof popup and the progress bar on `index.html`.

This is a genuine finding and it is **not** what it was reported as. It is not
load on Ghawy's server. It is an undocumented third-party data dependency on the
public landing page, polled every 5 and every 10 seconds by every visitor, whose
data (`purchases`: names and timestamps) lives outside this system entirely.
Recorded in [`FINDINGS.md`](FINDINGS.md); the decision about it belongs to
Phase 4 and to the owner, not to Phase 0.

## 3. Frontend call-site duplication

197 call sites resolve to 122 distinct method+path pairs. The duplication is
almost entirely the chat/DM copy-paste:

| Path | Call sites | Files |
|---|---:|---|
| `GET /profile/me` | 14 | admin-courses.js, chat.html, course-detail.html, course-details.html, courses.js, … |
| `GET /profile/{id}/public` | 4 | ai-updates.js, chat.html, direct-messages.html, profile.js |
| `GET /chat/online-count` | 3 | chat.html, direct-messages.html, dashboard.js* |
| `GET /chat/dm/list` | 3 | chat.html, direct-messages.html, utils.js |
| 20 further `/chat/*` and `/posts/*` paths | 2 each | chat.html **and** direct-messages.html |

\* `dashboard.js` is loaded by no page — see [`INVENTORY.md`](INVENTORY.md).

`GET /profile/me` at 14 call sites and 5,732 live requests is the clearest
consolidation candidate in the codebase: it is the same "who am I" answer
fetched independently by nearly every module on a page.

The 24 paths called from both `chat.html` and `direct-messages.html` are the
API-level shadow of the ~5,500-line duplication that Phase 6 addresses.

## 4. Endpoints with no auth dependency (31 of 241)

Listed here with a Phase 0 *provisional* reading. **Phase 3 confirms each one by
testing it** — this table is a work list, not a verdict.

| Endpoint | Provisional | Why |
|---|---|---|
| `POST /auth/register` | public-by-design | signup; Turnstile-gated |
| `POST /auth/login` | public-by-design | login |
| `POST /auth/token` | public-by-design | OAuth2 password form |
| `POST /auth/verify-email` | public-by-design | holds a code |
| `POST /auth/resend-verification-code` | public-by-design | rate limiting is the control |
| `POST /auth/forgot-password` | public-by-design | account enumeration to check |
| `POST /auth/verify-reset-code` | public-by-design | code is the credential |
| `POST /auth/reset-password` | public-by-design | reset token is the credential |
| `GET /auth/google/login` | public-by-design | OAuth start |
| `GET /auth/google/callback` | public-by-design | OAuth return |
| `POST /auth/exchange` | **check** | handoff-token exchange; verify single-use + expiry |
| `POST /webhooks/kashier` | public-by-design | signature-verified, external caller |
| `GET /payment/kashier/success` | public-by-design | browser return; signature-checked |
| `GET /payment/kashier/fail` | public-by-design | browser return |
| `POST /atlas/send-otp` | **check** | OTP send — brute force / mail flooding |
| `POST /atlas/verify-otp` | **check** | OTP verify — attempt limiting |
| `GET /birthday/claim` | public-by-design | authorised by a signed JWT in the query; email link |
| `GET /stats/public` | public-by-design | cached 5 min, aggregate only |
| `GET /courses` | public-by-design | catalogue; confirmed not to leak `pdf_url` |
| `GET /courses/{id}/reviews` | **check** | confirm it exposes no member PII |
| `GET /chat/online-count` | **check** | a bare count, but it is member-community data |
| `GET /guests/` | **check** | guest list |
| `GET /guests/stats` | **check** | guest stats |
| `GET /guests/sessions/` | **check** | guest sessions |
| `GET /guests/{id}` | **check** | single guest by client-supplied id |
| `GET /api/live-sessions` | **check** | explicitly named "legacy" |
| `WS /api/live-sessions/ws` | **check** | legacy socket; auth path unclear |
| `WS /ws` | by-design | auth is the first message, not a dependency (`ws.py:71`) |
| `DELETE /files/session` | **check** | ends a file session; what does it accept? |
| `GET /` | public-by-design | health/liveness |
| `GET /config/payment-info` | **check** | confirm it exposes no secret |

Fourteen marked **check**. That is the Phase 3 intake list, in addition to the
full IDOR sweep across every endpoint that accepts a client-supplied id.

## 5. Per-endpoint review questions

Rather than repeat nine columns for 241 rows, the questions from the brief are
answered where the answer is anything other than "no":

**Requested too frequently** — the eight polling entries in §2.

**Can be combined** — `/notifications/`, `/chat/community/unread` and
`/ai-updates/unread` fire together on the same 30s timer from the same module
and each returns a small badge count; they are one request. `/chat/dm/list` on
the same tick is a fourth.

**Can return less data** — `GET /chat/dm/list` at 23,536 requests returns a full
conversation list where the poll only needs an unread count and a change token.

**Needs caching** — `GET /stats/public` already caches 5 minutes with
single-flight. `GET /chat/online-count` has a microcache. `GET /courses` is a
near-static catalogue served on every dashboard load.

**Needs pagination** — the AI Updates feed is already a paginated archive (the
old 7-day filter was the "posts disappear" bug and must not come back).
`GET /chat/channels/{id}/messages` paginates. Admin member listings are the
place to check.

**Triggers unnecessary DB queries** — Phase 4 sweeps for `.all()` followed by
relationship access. `admin.students_progress` is the reference for how it
should look: grouped aggregate queries, no per-row fan-out.

**Already fixed, do not re-fix** — the community courses page previously called
`/courses/{id}/progress` once per course. It now makes three parallel calls
(`/courses`, `/courses/progress/summary`, `/courses/stats`) and the reasoning is
documented in the header of `courses.js`. `/courses/{id}/progress` still exists
and still serves the course-detail page.

---

## 6. Full endpoint table

Auth column: the dependency in the signature. `PERM_*` means
`Depends(require_perm(PERM_*))`.

### `admin.py` — 27 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/admin/analytics/kpis` | get_current_user | team.js |
| GET | `/admin/analytics/members-over-time` | get_current_user | team.js |
| GET | `/admin/analytics/payment-method-breakdown` | get_current_user | team.js |
| GET | `/admin/analytics/revenue-by-month` | get_current_user | team.js |
| GET | `/admin/analytics/revenue-over-time` | get_current_user | team.js |
| GET | `/admin/analytics/subscription-breakdown` | get_current_user | team.js |
| GET | `/admin/notes/{user_id}` | get_current_user | chat.html, direct-messages.html |
| POST | `/admin/notes/{user_id}` | get_current_user | chat.html, direct-messages.html |
| GET | `/admin/payments` | get_current_user | team.js |
| GET | `/admin/payments/export-csv` | get_current_user | _none found_ |
| GET | `/admin/payments/stats` | get_current_user | _none found_ |
| POST | `/admin/payments/{payment_id}/refund` | get_current_user | team.js |
| POST | `/admin/payments/{payment_id}/retry` | get_current_user | team.js |
| GET | `/admin/staff` | get_current_user | _none found_ |
| GET | `/admin/staff/roles` | get_current_user | _none found_ |
| PUT | `/admin/staff/{user_id}/permissions` | get_current_user | _none found_ |
| GET | `/admin/students-progress` | get_current_user | team.js |
| GET | `/admin/students-progress/{user_id}/courses/{course_id}/lessons` | get_current_user | team.js |
| GET | `/admin/users` | get_current_user | _none found_ |
| POST | `/admin/users/add` | get_current_user | _none found_ |
| DELETE | `/admin/users/{user_id}` | get_current_user | team.js |
| POST | `/admin/users/{user_id}/reset-password` | get_current_user | team.js |
| PATCH | `/admin/users/{user_id}/set-subscription` | get_current_user | team.js |
| PUT | `/admin/users/{user_id}/team-role` | get_current_user | _none found_ |
| PATCH | `/admin/users/{user_id}/toggle-active` | get_current_user | team.js |
| PATCH | `/admin/users/{user_id}/toggle-admin` | get_current_user | _none found_ |
| PATCH | `/admin/users/{user_id}/toggle-owner` | get_current_user | team.js |

### `ai_updates.py` — 14 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| DELETE | `/ai-updates/comments/{comment_id}` | get_current_active_member | ai-updates.js |
| GET | `/ai-updates/overview` | get_current_active_member | ai-updates.js |
| GET | `/ai-updates/polls/{poll_id}/results` | get_current_active_member | _none found_ |
| POST | `/ai-updates/polls/{poll_id}/vote` | get_current_active_member | ai-updates.js |
| GET | `/ai-updates/posts` | get_current_active_member | ai-updates.js |
| POST | `/ai-updates/posts` | get_current_admin_user | ai-updates.js |
| DELETE | `/ai-updates/posts/{post_id}` | get_current_admin_user | ai-updates.js |
| PATCH | `/ai-updates/posts/{post_id}` | get_current_admin_user | ai-updates.js |
| GET | `/ai-updates/posts/{post_id}/comments` | get_current_active_member | ai-updates.js |
| POST | `/ai-updates/posts/{post_id}/comments` | get_current_active_member | ai-updates.js |
| PATCH | `/ai-updates/posts/{post_id}/pin` | get_current_admin_user | ai-updates.js |
| POST | `/ai-updates/posts/{post_id}/react` | get_current_active_member | ai-updates.js |
| PUT | `/ai-updates/read` | get_current_active_member | ai-updates.js |
| GET | `/ai-updates/unread` | get_current_active_member | utils.js |

### `atlas.py` — 2 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/atlas/send-otp` | — | _none found_ |
| POST | `/atlas/verify-otp` | — | _none found_ |

### `birthday.py` — 4 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/birthday/claim` | — | _none found_ |
| GET | `/birthday/claims` | get_current_user | _none found_ |
| POST | `/birthday/claims/{claim_id}/approve` | get_current_user | _none found_ |
| POST | `/birthday/claims/{claim_id}/reject` | get_current_user | _none found_ |

### `chat.py` — 24 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/chat/admins` | get_current_active_member | utils.js |
| POST | `/chat/avatar` | get_current_active_member | _none found_ |
| GET | `/chat/channels` | get_current_active_member | _none found_ |
| POST | `/chat/channels` | get_current_active_member | _none found_ |
| POST | `/chat/channels/{channel_id}/join` | get_current_active_member | _none found_ |
| GET | `/chat/channels/{channel_id}/members` | get_current_active_member | _none found_ |
| GET | `/chat/channels/{channel_id}/messages` | get_current_active_member | _none found_ |
| POST | `/chat/channels/{channel_id}/messages` | get_current_active_member | _none found_ |
| PUT | `/chat/channels/{channel_id}/read` | get_current_active_member | _none found_ |
| PUT | `/chat/community/read` | get_current_active_member | chat.html |
| GET | `/chat/community/unread` | get_current_active_member | utils.js |
| POST | `/chat/dm` | get_current_active_member | chat.html, direct-messages.html |
| GET | `/chat/dm/list` | get_current_active_member | chat.html, direct-messages.html, utils.js |
| PUT | `/chat/dm/read` | get_current_active_member | chat.html, direct-messages.html |
| POST | `/chat/mark-read` | get_current_active_member | chat.html, direct-messages.html |
| GET | `/chat/members` | get_current_active_member | chat.html, direct-messages.html |
| GET | `/chat/messages` | get_current_active_member | chat.html, dashboard.js, direct-messages.html |
| POST | `/chat/messages` | get_current_active_member | chat.html, dashboard.js, direct-messages.html |
| DELETE | `/chat/messages/{message_id}` | get_current_active_member | chat.html, direct-messages.html |
| PUT | `/chat/messages/{message_id}` | get_current_active_member | chat.html, direct-messages.html |
| GET | `/chat/online-count` | — | chat.html, dashboard.js, direct-messages.html |
| GET | `/chat/start-here-config` | get_current_active_member | direct-messages.html |
| PUT | `/chat/start-here-config` | get_current_active_member | direct-messages.html |
| POST | `/chat/upload` | get_current_active_member | _none found_ |

### `coupons.py` — 4 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/coupons/admin` | get_current_user | _none found_ |
| POST | `/coupons/admin` | get_current_user | _none found_ |
| PATCH | `/coupons/admin/{coupon_id}` | get_current_user | _none found_ |
| POST | `/coupons/preview` | get_current_user | pay.js, pricing.js |

### `courses.py` — 33 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/courses` | — | catalog.js, courses.js |
| GET | `/courses/admin/all` | PERM_COURSES | _none found_ |
| GET | `/courses/admin/courses` | PERM_COURSES | _none found_ |
| POST | `/courses/admin/courses` | PERM_COURSES | _none found_ |
| PATCH | `/courses/admin/courses/reorder` | PERM_COURSES | _none found_ |
| PATCH | `/courses/admin/courses/{course_id}` | PERM_COURSES | _none found_ |
| DELETE | `/courses/admin/courses/{course_id}` | PERM_COURSES | _none found_ |
| POST | `/courses/admin/courses/{course_id}/upload-pdf` | PERM_COURSES | _none found_ |
| POST | `/courses/admin/courses/{course_id}/upload-thumbnail` | PERM_COURSES | _none found_ |
| PATCH | `/courses/admin/lessons/{lesson_id}` | PERM_COURSES | admin-courses.js |
| DELETE | `/courses/admin/lessons/{lesson_id}` | PERM_COURSES | admin-courses.js |
| POST | `/courses/admin/lessons/{lesson_id}/pdfs` | PERM_COURSES | _none found_ |
| DELETE | `/courses/admin/lessons/{lesson_id}/pdfs` | PERM_COURSES | _none found_ |
| GET | `/courses/admin/lessons/{lesson_id}/status` | PERM_COURSES | admin-courses.js |
| POST | `/courses/admin/{course_id}/certificate` | PERM_COURSES | _none found_ |
| DELETE | `/courses/admin/{course_id}/certificate` | PERM_COURSES | _none found_ |
| GET | `/courses/admin/{course_id}/lessons` | PERM_COURSES | admin-courses.js |
| POST | `/courses/admin/{course_id}/lessons` | PERM_COURSES | admin-courses.js |
| GET | `/courses/progress/summary` | get_current_active_member | _none found_ |
| GET | `/courses/stats` | get_current_active_member | _none found_ |
| GET | `/courses/{course_id}` | get_current_user_optional | catalog.js, course-detail.html |
| POST | `/courses/{course_id}/lessons` | PERM_COURSES | course-detail.html |
| GET | `/courses/{course_id}/lessons` | get_current_user | course-detail.html |
| PATCH | `/courses/{course_id}/lessons/{lesson_id}` | PERM_COURSES | _none found_ |
| POST | `/courses/{course_id}/lessons/{lesson_id}/complete` | get_current_active_member | course-detail.html |
| DELETE | `/courses/{course_id}/lessons/{lesson_id}/complete` | get_current_active_member | course-detail.html |
| PATCH | `/courses/{course_id}/lessons/{lesson_id}/duration` | get_current_user | course-detail.html |
| GET | `/courses/{course_id}/lessons/{lesson_id}/vdo-otp` | get_current_user | course-detail.html |
| GET | `/courses/{course_id}/progress` | get_current_user | course-detail.html |
| GET | `/courses/{course_id}/reviews` | — | course-detail.html |
| POST | `/courses/{course_id}/reviews` | get_current_user | course-detail.html |
| DELETE | `/courses/{course_id}/reviews/{review_id}` | PERM_COURSES | course-detail.html |
| GET | `/courses/{course_id}/top-students` | get_current_user | course-detail.html |

### `dashboard.py` — 1 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/dashboard/summary` | get_current_active_member | dashboard.js, profile.js |

### `email_campaigns.py` — 11 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/admin/email-campaigns/atlas-recipients` | get_current_user | _none found_ |
| POST | `/admin/email-campaigns/audience-quality` | get_current_user | team.js |
| GET | `/admin/email-campaigns/campaigns` | get_current_user | team.js |
| POST | `/admin/email-campaigns/campaigns` | get_current_user | team.js |
| GET | `/admin/email-campaigns/campaigns/{campaign_id}` | get_current_user | team.js |
| PUT | `/admin/email-campaigns/campaigns/{campaign_id}` | get_current_user | team.js |
| POST | `/admin/email-campaigns/campaigns/{campaign_id}/active` | get_current_user | team.js |
| POST | `/admin/email-campaigns/preview` | get_current_user | team.js |
| GET | `/admin/email-campaigns/recipients` | get_current_user | _none found_ |
| POST | `/admin/email-campaigns/send` | get_current_user | team.js |
| GET | `/admin/email-campaigns/status` | get_current_user | team.js |

### `exams.py` — 8 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/admin/courses/{course_id}/exams` | PERM_COURSES | _none found_ |
| POST | `/admin/courses/{course_id}/exams` | PERM_COURSES | _none found_ |
| GET | `/admin/exams/{exam_id}` | PERM_COURSES | _none found_ |
| PATCH | `/admin/exams/{exam_id}` | PERM_COURSES | _none found_ |
| DELETE | `/admin/exams/{exam_id}` | PERM_COURSES | _none found_ |
| GET | `/courses/{course_id}/exams` | get_current_active_member | course-detail.html |
| GET | `/exams/{exam_id}` | get_current_active_member | course-detail.html |
| POST | `/exams/{exam_id}/submit` | get_current_active_member | course-detail.html |

### `feedbacks.py` — 5 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/feedbacks/` | get_current_active_member | _none found_ |
| GET | `/feedbacks/` | get_current_active_member | _none found_ |
| GET | `/feedbacks/admin` | PERM_FEEDBACKS | _none found_ |
| POST | `/feedbacks/upload-image` | PERM_FEEDBACKS | _none found_ |
| DELETE | `/feedbacks/{feedback_id}` | PERM_FEEDBACKS | _none found_ |

### `files.py` — 3 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/files/session` | get_current_user | _none found_ |
| DELETE | `/files/session` | — | _none found_ |
| GET | `/files/{category}/{filename}` | file_requester | _none found_ |

### `google_auth.py` — 3 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/auth/exchange` | — | _none found_ |
| GET | `/auth/google/callback` | — | _none found_ |
| GET | `/auth/google/login` | — | _none found_ |

### `guests.py` — 14 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/guests/` | — | goh.js |
| POST | `/guests/` | get_current_active_member | goh.js |
| GET | `/guests/sessions/` | — | goh.js |
| POST | `/guests/sessions/` | get_current_active_member | goh.js |
| PUT | `/guests/sessions/{session_id}` | get_current_active_member | _none found_ |
| DELETE | `/guests/sessions/{session_id}` | get_current_active_member | _none found_ |
| GET | `/guests/stats` | — | goh.js |
| GET | `/guests/suggest` | get_current_active_member | goh.js |
| POST | `/guests/suggest` | get_current_active_member | goh.js |
| DELETE | `/guests/suggest/{suggestion_id}` | get_current_active_member | _none found_ |
| POST | `/guests/upload-avatar` | get_current_active_member | _none found_ |
| GET | `/guests/{guest_id}` | — | _none found_ |
| PUT | `/guests/{guest_id}` | get_current_active_member | _none found_ |
| DELETE | `/guests/{guest_id}` | get_current_active_member | _none found_ |

### `help_center.py` — 1 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/help-center/team` | get_current_active_member | _none found_ |

### `live.py` — 11 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/admin/live/sessions` | PERM_LIVE | _none found_ |
| GET | `/admin/live/sessions` | PERM_LIVE | _none found_ |
| PATCH | `/admin/live/sessions/{session_id}` | PERM_LIVE | _none found_ |
| DELETE | `/admin/live/sessions/{session_id}` | PERM_LIVE | _none found_ |
| GET | `/admin/live/sessions/{session_id}/attendees` | PERM_LIVE | _none found_ |
| POST | `/admin/live/sessions/{session_id}/notify` | PERM_LIVE | _none found_ |
| GET | `/api/live-sessions` | — | _none found_ |
| WEBSOCKET | `/api/live-sessions/ws` | — | _none found_ |
| GET | `/live/sessions` | get_current_user | _none found_ |
| POST | `/live/sessions/{session_id}/register` | get_current_user | _none found_ |
| DELETE | `/live/sessions/{session_id}/register` | get_current_user | _none found_ |

### `main.py` — 5 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/` | — | _none found_ |
| GET | `/config/payment-info` | — | pay.js |
| DELETE | `/payments/{payment_id}` | get_current_admin_user | _none found_ |
| PATCH | `/users/me/complete-onboarding` | get_current_user | onboarding.js |
| DELETE | `/users/{user_id}` | get_current_admin_user | _none found_ |

### `manual_payments.py` — 9 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/manual-payments` | get_current_user | _none found_ |
| GET | `/manual-payments/my-status` | get_current_user | _none found_ |
| GET | `/manual-payments/stats` | get_current_user | _none found_ |
| GET | `/manual-payments/status/{email}` | get_current_user | _none found_ |
| POST | `/manual-payments/submit` | get_current_user | pay.js |
| GET | `/manual-payments/{request_id}` | get_current_user | _none found_ |
| POST | `/manual-payments/{request_id}/approve` | get_current_user | _none found_ |
| POST | `/manual-payments/{request_id}/reject` | get_current_user | _none found_ |
| POST | `/manual-payments/{request_id}/resend-invite` | get_current_user | _none found_ |

### `notifications.py` — 3 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/notifications/` | get_current_user | chat.html, utils.js |
| PATCH | `/notifications/read-all` | get_current_user | utils.js |
| PATCH | `/notifications/{notif_id}/read` | get_current_user | chat.html, utils.js |

### `payment.py` — 3 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/payment/kashier/create` | get_current_user | pricing.js, renewal.js |
| GET | `/payment/kashier/fail` | — | _none found_ |
| GET | `/payment/kashier/success` | — | _none found_ |

### `posts.py` — 14 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/posts/comments/{comment_id}/react` | get_current_active_member | chat.html |
| GET | `/posts/{channel}` | get_current_active_member | chat.html, direct-messages.html |
| POST | `/posts/{channel}` | get_current_active_member | chat.html, direct-messages.html |
| GET | `/posts/{channel}/pinned` | get_current_active_member | chat.html, direct-messages.html |
| GET | `/posts/{channel}/top-topics` | get_current_active_member | chat.html, direct-messages.html |
| GET | `/posts/{channel}/{post_id:int}` | get_current_active_member | chat.html, direct-messages.html |
| PATCH | `/posts/{channel}/{post_id:int}` | get_current_active_member | chat.html, direct-messages.html |
| DELETE | `/posts/{channel}/{post_id:int}` | get_current_active_member | chat.html, direct-messages.html |
| PATCH | `/posts/{channel}/{post_id:int}/pin` | get_current_active_member | chat.html, direct-messages.html |
| GET | `/posts/{post_id}/comments` | get_current_active_member | chat.html, direct-messages.html |
| POST | `/posts/{post_id}/comments` | get_current_active_member | chat.html, direct-messages.html |
| PATCH | `/posts/{post_id}/comments/{comment_id}` | get_current_active_member | chat.html, direct-messages.html |
| DELETE | `/posts/{post_id}/comments/{comment_id}` | get_current_active_member | chat.html, direct-messages.html |
| POST | `/posts/{post_id}/react` | get_current_active_member | chat.html |

### `profile.py` — 14 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/profile/avatar` | get_current_active_member | _none found_ |
| POST | `/profile/change-password` | get_current_active_member | profile.js |
| POST | `/profile/complete-onboarding` | get_current_active_member | onboarding.js |
| POST | `/profile/heartbeat` | get_current_active_member | utils.js |
| GET | `/profile/me` | get_current_active_member | admin-courses.js, chat.html, course-detail.html, course-details.html, courses.js, dashboard.js, direct-messages.html, goh.js, index.html, login.js, onboarding.js, profile.js, renewal.js, utils.js |
| PUT | `/profile/me` | get_current_active_member | profile.js |
| POST | `/profile/offline` | get_current_active_member | utils.js |
| GET | `/profile/onboarding-status` | get_current_active_member | _none found_ |
| POST | `/profile/send-phone-otp` | get_current_active_member | onboarding.js |
| GET | `/profile/subscription-info` | get_current_user | profile-settings.html, renewal.js |
| POST | `/profile/upload-avatar` | get_current_active_member | onboarding.js |
| POST | `/profile/verify-phone-otp` | get_current_active_member | onboarding.js |
| GET | `/profile/{user_id}` | get_current_active_member | _none found_ |
| GET | `/profile/{user_id}/public` | get_current_active_member | ai-updates.js, chat.html, direct-messages.html, profile.js |

### `projects.py` — 10 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/admin/projects` | PERM_PROJECTS | _none found_ |
| GET | `/admin/projects/{project_id}` | PERM_PROJECTS | _none found_ |
| DELETE | `/admin/projects/{project_id}` | PERM_PROJECTS | _none found_ |
| POST | `/admin/projects/{project_id}/approve` | PERM_PROJECTS | _none found_ |
| GET | `/admin/projects/{project_id}/download` | PERM_PROJECTS | team.js |
| POST | `/admin/projects/{project_id}/notes` | PERM_PROJECTS | _none found_ |
| POST | `/admin/projects/{project_id}/request-changes` | PERM_PROJECTS | _none found_ |
| GET | `/projects/my-projects` | get_current_active_member | course-detail.html |
| POST | `/projects/submit` | get_current_active_member | _none found_ |
| GET | `/projects/{project_id}` | get_current_active_member | _none found_ |

### `reports.py` — 4 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/reports/` | get_current_active_member | _none found_ |
| GET | `/reports/admin` | PERM_REPORTS | _none found_ |
| GET | `/reports/my` | get_current_active_member | _none found_ |
| DELETE | `/reports/{report_id}` | PERM_REPORTS | _none found_ |

### `stats.py` — 1 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/stats/public` | — | main.js |

### `users.py` — 11 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| GET | `/auth` | get_current_active_member | _none found_ |
| DELETE | `/auth/account` | get_current_user | profile.js |
| POST | `/auth/forgot-password` | — | reset-password.js |
| POST | `/auth/login` | — | index.html, login.js |
| POST | `/auth/logout-all` | get_current_user | _none found_ |
| POST | `/auth/register` | — | index.html, register.js |
| POST | `/auth/resend-verification-code` | — | verify-email.js |
| POST | `/auth/reset-password` | — | reset-password.js |
| POST | `/auth/token` | — | _none found_ |
| POST | `/auth/verify-email` | — | verify-email.js |
| POST | `/auth/verify-reset-code` | — | reset-password.js |

### `webhooks.py` — 1 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| POST | `/webhooks/kashier` | — | _none found_ |

### `ws.py` — 1 endpoints

| Method | Path | Auth dependency | Frontend caller |
|---|---|---|---|
| WEBSOCKET | `/ws` | — | _none found_ |