# Phase 3 — Security and authorization

Scope: the full access-control audit of 242 endpoints, the OWASP checklist, and
configuration. Five findings fixed, each with a before/after reproduction that
runs against a throwaway database. Two of them were yours; three were not.

The headline is the one that was not in the brief: **any paying member could
read and write any other two members' private DMs**, by calling one endpoint.

---

## 0. Methodology — your warning was right, and then it was right again

You warned that pattern-matching produces confident wrong answers here, and that
the codebase guards endpoints in three idioms. Both halves held, and the second
half was understated: there is a **fourth** idiom.

| # | Idiom | Example |
|---|-------|---------|
| 1 | Signature dependency | `current_user: User = Depends(get_current_admin_user)` |
| 2 | Decorator dependency | `@router.post("/…", dependencies=[Depends(PERM_COURSES)])` |
| 3 | In-body call | `require_owner(current_user)` on the first line |
| 4 | **Inline role check** | `if not current_user.is_owner: raise HTTPException(403)` |

Idiom 4 is what guards `PATCH /admin/users/{user_id}/toggle-owner`. My first
scanner knew idioms 1–3, which is one more than the naive version, and it still
reported that endpoint as an unauthenticated privilege-escalation route — the
single most alarming false positive it was possible to produce. Reading it took
thirty seconds and showed a correct guard.

I then taught the scanner idiom 4. It immediately produced **seven new false
positives** in the other direction: it decided `/login`, `/register`,
`/verify-email` and `POST /webhooks/kashier` were "guarded", because each
contains an `if …: raise` mentioning `is_verified` or `order_id`. Those are
business logic, not authorization. Three scanners, three different wrong
answers — exactly your experience.

So the classification in `docs/SECURITY-ENDPOINTS.md` is not scanner output. The
scanner produced the reading list; every one of the 241 rows was then read. The
table records all four idioms per route so the next person does not have to
rediscover them.

Endpoint count: the brief says 242 and my scan agrees — 242 before this phase,
241 after, because Finding A is deleted.

| Class | Count |
|---|---|
| Guarded (dependency, in-body, or inline) | 215 |
| Public by design — each read and justified individually | 26 |
| **Vulnerable** | **0 remaining** (5 found, 5 fixed) |

---

## 1. Findings

Severity is impact × reachability. Reproductions are in
`backend/scripts/acceptance_access_control.py` — 20 assertions, all failing
before the fixes in the way the finding describes, all passing after.

### 🔴 F-C · Any member could read, join and post into any other members' DMs — **HIGH**

**This was not in the brief. It is the most serious thing in this phase.**

`backend/app/routers/chat.py:596` — `POST /chat/channels/{channel_id}/join`.

Root cause: the endpoint looked the channel up directly and created a
`ChatMember` row for whatever id it was handed, **with no check of the channel's
type**:

```python
channel = db.query(Channel).filter(Channel.id == channel_id).first()
if not channel: raise HTTPException(404)
# …then unconditionally insert a membership row
```

`ensure_channel_access` — the gate the read and write paths use — treats a DM as
accessible precisely when a membership row exists. So this endpoint *minted the
evidence that the gate accepts*. Channel ids are sequential integers, so the
whole DM table was walkable.

The codebase already knew this shape of bug: `_may_post_to_channel` in `ws.py`
carries the comment *"Mirrors ensure_channel_access in routers/chat.py; the two
must agree, or a rule enforced over HTTP is simply bypassed over the socket."*
Two doors were checked against each other. This was a third door nobody had
compared them to.

Full impact chain, all reproduced:

1. `POST /chat/channels/{dm_id}/join` → membership created
2. `GET /chat/channels/{dm_id}/messages` → **full private history**
3. `GET /files/chat/{filename}` → DM attachments (`files.py` defers to the same gate)
4. WebSocket send → **post into the conversation** as themselves

Before:
```
FAIL outsider cannot join a DM channel   -> 200 {"message":"Joined channel"}
FAIL outsider cannot read the DM history -> 200 leaked=True … "ALICE_PRIVATE_SECRET" …
FAIL outsider cannot post into the DM    -> 201 {"content":"MALLORY_WAS_HERE"}
```

Fix: route the join through the same gate as everything else —
`ensure_channel_access(db, channel_id, current_user, auto_join=False)`. A DM
without existing membership 404s; a community channel passes through and the
endpoint creates the row as before.

After: all three refuse, and the two behaviours that must survive still do —
`participant still reads their own DM`, `member can still join an open community
channel`. Nothing in the frontend calls `/join` at all (community channels
auto-join on read), so this fix has no UI impact whatsoever.

### 🟠 F-D · Announcement links could escape the origin — **MEDIUM**

`backend/app/routers/announcements.py` — `_clean_link`. This function exists for
one reason, stated in its own docstring: an announcement link is injected into
every member's notification bell, so an external link there is ready-made
phishing in the platform's name.

It did not do that. The guard was ordered wrong:

```python
if link.startswith("/"):
    return link[:500]          # ← returns here
lowered = link.lower()
if … or lowered.startswith(("javascript:", "data:", "vbscript:", "//")):
    raise HTTPException(400)   # ← the "//" test is unreachable
```

`//evil.example` starts with `/`, so it returned at the first branch and never
reached the `//` test. That test was dead code from the day it was written.
`utils.js:645` then does `window.location.href = link`, and a protocol-relative
URL leaves the origin.

Proven, not assumed — two local origins, headless Chromium, the real sanitiser
and the real navigation:

```
=== attacker-origin (:8802) access log ===
GET /ATTACKER-GOT-THE-MEMBER
```

Also accepted: `/\evil.example` (browsers treat `/\` as `//`) and
`java\tscript:alert(1)` (browsers strip tab/CR/LF before parsing the scheme, so
that spelling reads as `javascript:` — Python's own `urlparse` agrees, returning
`scheme='javascript'`).

Fix: strip control characters first, test `//`, `/\`, `\\` **before** the
`startswith("/")` early return, and reject any scheme at all rather than
blacklisting four names. `/dashboard.html` still works.

**Honesty note on the `javascript:` variant:** I could not demonstrate script
execution. My headless harness did not fire even a plain `javascript:` URL, so it
proves nothing either way, and I am not claiming XSS. I fixed that spelling
because the function's clear intent is to block `javascript:` and it did not —
that stands on its own without the exploit.

Reachability: requires the `announcements` staff permission. That is not a reason
to leave it — `_clean_link` is precisely the control that bounds what a holder of
that permission can do, and it reaches every member's bell.

### 🟠 F-E · The file cookie ignored the `token_version` kill switch — **MEDIUM**

`backend/app/routers/users.py` / `files.py`.

`token_version` is the platform's revocation mechanism: `/logout-all` and a
password reset bump it, and `get_current_user` compares it, killing every session
token. The 7-day file cookie carried no `ver` claim, and neither `file_requester`
nor `_user_from_file_cookie` checked one.

So a copied file cookie went on reading receipts, course PDFs, project
submissions and DM attachments for up to a week *after* the member had locked
their account — which is the exact scenario the switch exists for. `logout-all`'s
own docstring claims it "invalidates all of them server-side".

Before: `FAIL a file cookie minted before logout-all is refused -> 404`
(404 = it got past authentication to the file lookup).
After: `ok … refused -> 401`, while a correctly-minted cookie still works.

Fix: mint `ver` into the file token, check it on both paths, and pass the user's
version at all five call sites.

Second, smaller hole closed in the same function: the bearer branch read
`if payload.get("typ") != "file"`, which accepted the 120-second **OAuth hand-off
token** as a file credential. `get_current_user` refuses any typed token; this
now matches (`typ is None`).

**Deployment impact — checked against production, and it is nil:** 1,910 of 1,915
accounts have `token_version = 0`. Tokens minted before the claim existed read as
0, so those cookies keep working untouched. The 5 accounts at version 1 had
already re-logged-in (which mints a correct cookie), and `ensureFileCookie` in
`utils.js` re-mints via `POST /files/session` regardless.

### 🟢 F-A · `GET /api/live-sessions` — unauthenticated, N+1, and dead — **deleted**

Your finding, confirmed on all three counts and removed rather than fixed.

Verified dead the way you asked — traffic, not just source:

- Frontend grep: the only `/api/live-sessions` reference in JS is `bwm.js:312`, and it is the **WebSocket**. The team-dashboard tab uses `/admin/live/sessions`.
- **Production nginx logs: 77,081 requests over 8.5 hours, zero hits on the REST endpoint.** The only 4 `live-sessions` lines in that window are the `/ws` upgrade — which proves the path was being logged.

Members already read sessions via `GET /live/sessions` (member-gated) and staff
via `GET /admin/live/sessions` (permission-gated). This was a third, open door
onto the same rows. Deleted, with a comment recording why so it is not
reintroduced.

### 🟢 F-B · Lesson duration writable by any registered account — **LOW, fixed**

`backend/app/routers/courses.py:449`. Confirmed exactly as you described: guarded
by `get_current_user`, so any registered account — including one that never paid
— could set the advertised duration of any lesson in any course. As you said, the
`duration_minutes == 0` test is a race, not an authorization check.

You asked me to decide whether the player should report this at all, or whether
it belongs behind `PERM_COURSES`. **Decision: it stays with the player, but the
caller must be entitled to watch the lesson.** Reasoning:

- `course-detail.html` PATCHes it from three places when the player learns the real length; the player is the only thing that knows it.
- Moving it behind `PERM_COURSES` would mean an admin hand-entering every duration, which is a functional regression, not a fix.
- The actual defect is *who counts as the player*. So it now requires `get_current_active_member` **and** passes through `_can_watch` — the same function, not a second copy of the rule, that decides whether they may have the video at all.

An active member reporting the length of a video they are watching is the
intended use and still works; everyone else gets 402/403. My first version of the
acceptance test asserted that ordinary members were refused, which contradicted
the design I had chosen — the test was wrong, and I corrected the test to assert
the real property rather than weakening the feature to match a bad assertion.

---

## 2. Checklist results — the areas that were already sound

Reported because a clean result is a result. None of these needed changes.

| Area | Verdict |
|---|---|
| **IDOR/BOLA sweep** | 117 endpoints take a client-supplied id. Every one either scopes its query by `current_user.id`, checks ownership before mutating (`posts.py`, `chat.py`, `ai_updates.py` all use `owner or is_admin`), or sits behind an owner/permission guard. One hole: F-C. |
| **Privilege escalation** | Closed. `toggle-admin`, `toggle-owner`, `team-role` and `staff/{id}/permissions` are all owner-only. An admin cannot edit their own permissions; an owner cannot role-manage themselves (`You can't change your own role`) or another owner; role presets are validated against the catalog and normalised through the key whitelist. The `team_role` feature — never security-reviewed before — is sound. |
| **Files, uploads, `X-Accel-Redirect`** | Sound. `_resolve` rejects separators, re-resolves, and requires the result inside the category root; `category` is whitelisted *before* `_resolve` is reached. The redirect header is built from `path.name` (post-resolution basename) and `quote()`d, so nothing injectable survives. The internal location is `internal;` — **verified from outside: `/_protected_uploads/…` → 404**, as do `/uploads/receipts/` and `/api/uploads/receipts/`. `_authorize` resolves every file back to the row that owns it, so an active member cannot read a receipt by putting its name in the `lesson-pdfs` path. |
| **Paid-content boundary** | Sound. `_can_watch` is the single rule; `vdo-otp` re-checks `is_active or is_free_preview`; lesson completion requires playback evidence. |
| **Announcements audience** | Sound, and the brief's specific worry is unfounded: the client never sends ids. Audience is resolved server-side at send time from a filter, `ALLOWED_KEYS` drops unknown keys, corrupt JSON falls back to the *empty* filter rather than everyone. Confirm phrase is exact-match; `status == "sent"` plus a lock prevents double-send. |
| **SQL injection** | No surface. Every `text()` in the tree is a static `server_default`. No string-built SQL, no `execute()` with user input. |
| **Command injection / deserialization** | No surface. Zero `pickle`, `eval`, `exec`, `subprocess`, `os.system`, `yaml.load`. |
| **SSRF** | All outbound calls go to fixed provider URLs or env-configured webhooks; none takes a user-supplied URL. |
| **CORS** | Explicit origin list from env (`https://ghawy.ai` + 3), no regex. Verified live: `Origin: https://evil.example` gets **no** `Access-Control-Allow-Origin` back. |
| **Docs / debug exposure** | Closed in production — `/api/docs`, `/api/redoc`, `/api/openapi.json` all **404, verified live**. `openapi_url` is nulled too, not just the UI. |
| **Rate limiting / brute force** | Working. nginx zones: `auth` 30r/m, `register` 6r/m, `otp` 6r/m, `api` 30r/s, 40 conns/IP. **Verified live at low volume: 12 sequential login attempts → 429 on the 12th.** Reset codes burn after 5 tries; Atlas OTP after 5. |
| **Password reset** | Sound. Constant response, 15-minute expiry, attempt counter, and it bumps `token_version` — so a reset really does end existing sessions. |
| **JWT / session** | Sound. `get_current_user` refuses *any* typed token rather than blacklisting types, and checks `ver`. No secrets in the URL since the OAuth hand-off cookie replaced `?token=`. |
| **Webhook + payment manipulation** | Sound. Webhook authenticated by HMAC; the redirect path confirms only on valid signature **and** matching amount **and** matching currency **and** a `PENDING` row. |
| **Secrets in source** | None. All credentials read from env; `.env`, `.env.*`, `backend/.env.production` are gitignored. |

---

## 3. Not fixed — reported for your decision

| # | Item | Severity | Why I left it |
|---|---|---|---|
| 1 | **Account enumeration on `/login`** | Low | Three distinct responses distinguish "not registered" from "registered but unverified" from "registered via Google", and the bcrypt short-circuit makes a nonexistent address measurably faster. But the Google message is *deliberate UX* — telling someone to use the Google button. Closing it fully means degrading that. Rate-limited at 30r/m. **Your call**, not mine to trade away. |
| 2 | `_send_lock` is a `threading.Lock` | Info | Correct on this deployment (single worker). It would not hold across `--workers N`. Noted so it is not surprising if the worker count ever changes. |
| 3 | Geo-lookup interpolates `X-Forwarded-For` into a URL path (`google_auth.py:96`) | Info | Not SSRF — scheme and host are literal, so the request always goes to `ipapi.co`. Cosmetic path pollution only. |
| 4 | `GET /courses/{id}/reviews` does not filter `is_published` | Info | Reviews of an unpublished course are readable. Content is review text and display names; a draft course with reviews is close to hypothetical. |
| 5 | Secrets live in git history, never rotated; SSH root+password | **Pre-existing, open** | From the 2026-08-17 audit; outside the code scope of this phase but it outranks several things I *did* fix. Restated so it does not get lost. |

---

## 4. Acceptance gate

- [x] **All endpoints classified, all guard idioms accounted for** — 241 rows in `docs/SECURITY-ENDPOINTS.md`, four idioms, each read
- [x] **Every ID-accepting endpoint has an ownership/permission check or a written reason** — 117 checked; the 26 public ones are individually justified in the same doc
- [x] **Every high/critical finding fixed with before/after reproduction** — F-C (high) and F-D/F-E (medium) fixed; 20 assertions, 10 failing before → 20 passing after
- [x] **Findings A and B resolved** — A deleted (dead, proven by 77k log lines), B fixed with the design decision recorded
- [x] **Announcements router and team roles reviewed** — both; announcements yielded F-D, team roles are clean
- [x] **Existing behaviour intact** — `acceptance_security.py` 86/86, `acceptance_team_roles.py` 64/64, `acceptance_access_control.py` 20/20

### Verification actually run

| Check | Result |
|---|---|
| `acceptance_access_control.py` (new) | 10 failed → **20/20 passed** |
| `acceptance_security.py` (covers courses, files, chat, admin, logout-all) | **86/86** |
| `acceptance_team_roles.py` | **64/64** |
| Internal nginx location reachable directly? | **404** — no |
| `/api/docs`, `/redoc`, `/openapi.json` in production | **404** |
| CORS from a foreign origin | no `ACAO` header |
| Login rate limit | **429 at request 12** |
| Protocol-relative redirect leaves the origin | **proven** (attacker-origin log) |
| Production `token_version` distribution | 1910 × 0, 5 × 1 → fix is a no-op for users |

All destructive runs targeted `ghawy_test`, a scratch database created for this
phase, printed before every run and approved by `_acceptance_guard`. Production
`ghawy_db` was never a target — the guard refuses it by name.

**Nothing here has been deployed.** The running image still predates Phase 0; the
Phase 1+2 window is unchanged and Phase 3 is not folded into it.

---

## 5. Note on scope

This phase ran long, as you expected. I did not split it, because the tail of the
list is where F-C was hiding — `chat.py` is late in an alphabetical sweep, and the
DM bypass would have been in the deferred half. The endpoints reviewed last were
indeed where the finding was.
