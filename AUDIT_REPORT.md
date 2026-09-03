# Ghawy Project Audit Report

> ## ⚠️ Status: SUPERSEDED — corrected 2026-09-03
>
> This report was written before launch. **Every one of its four "critical"
> issues is now closed**: three were fixed in the code, and the fourth was never
> real. Its two remaining open items are minor and are restated accurately
> below.
>
> Leaving it as it stood was the dangerous option: it named `main.py:494` and
> `:503` as unauthenticated when those lines are admin-guarded, and it described
> the migration tree as broken over a revision id that does not exist anywhere
> in the repository. An audit document that reports fixed problems as open
> teaches the reader to ignore it.
>
> Each item below was **re-verified against the code on 2026-09-03**, with the
> evidence quoted. The current audit lives in [`docs/`](docs/):
> [ARCHITECTURE](docs/ARCHITECTURE.md) · [API-MAP](docs/API-MAP.md) ·
> [INVENTORY](docs/INVENTORY.md) · [BASELINE](docs/BASELINE.md) ·
> [FINDINGS](docs/FINDINGS.md).

---

## 🔴 Critical Issues — all four closed

### ✅ Issue 1 — Unprotected `delete_user` / `delete_payment` — FIXED

Both endpoints now require an admin. `backend/main.py:341` and `:354`:

```python
@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(get_current_admin_user)):
```

(The line numbers in the original report, 494 and 503, no longer correspond to
these functions.)

### ✅ Issue 2 — Kashier webhook signature bypass — FIXED

The webhook no longer warns and continues. `backend/app/routers/webhooks.py:134`:

```python
if not received_signature:
    raise HTTPException(status_code=401, detail="Missing signature")
if not verify_kashier_webhook(data, received_signature):
    raise HTTPException(status_code=401, detail="Invalid signature")
```

It additionally rejects amount and currency mismatches (lines 169–179). The
signature checked is the `x-kashier-signature` header — sorted keys, RFC3986,
API key. The body's `hash` field is not usable for this and is not used.

### ✅ Issue 3 — `.env` missing from `.gitignore` — FIXED

`.gitignore:17-21` covers `.env`, `.env.*`, `backend/.env` and
`backend/.env.production`, with `!.env.example` re-included.

> Not fixed by this, and still open: secrets committed **before** the ignore
> rule was added remain in git history, and have never been rotated. That is
> tracked as a live security item, not as part of this issue.

### ❌ Issue 4 — "Broken Alembic migration tree" — WAS NEVER TRUE (and neither was its successor)

Two separate claims have been made about this tree. **Both were wrong, and the
real defect was something neither of them described.** Recording all three
together, because a stale finding left standing in the record is exactly the
failure mode this document exists to correct.

**Claim 1 — "`alembic check` cannot locate revision `8f370e02e750`."** That
revision id appears nowhere in the repository — not as a `revision`, not as a
`down_revision`, not in any file under `backend/`.

**Claim 2 — "3 heads, 2 roots and a fork; `alembic upgrade head` fails
outright."** Listed as finding #3 of the phased-audit brief, with heads
`b3d7e91c2a45`, `307efdf1db45`, `c1a7f4e9b8d2` and roots `4823c6c0b288`,
`2668e3beafa9`. Also false, and confirmed independently by the owner
(2026-09-03).

`4823c6c0b288` is a **merge revision**. Its parent is a two-element tuple that
spans two lines:

```python
down_revision: Union[str, Sequence[str], None] = (
    '307efdf1db45', 'c1a7f4e9b8d2'
)
```

A regex that only matches a quoted string or `None` matches neither line, so it
reads `4823c6c0b288` as parentless — a phantom second root — and reads its two
real parents as revisions nobody points at — phantom heads. A tuple-aware parse
returns **exactly one head and one root**. So does alembic:

```
$ docker exec ghawy_backend alembic heads
c9e1d3a7b542 (head)
$ docker exec ghawy_backend alembic current
c9e1d3a7b542 (head)
```

The fork at `f1201efadb0f` is real and has always been closed by that merge.
No merge revision was needed in Phase 1, and no `down_revision` was edited to
silence an error.

> **A caution for anyone re-auditing this.** Ask alembic. Do not grep. Both
> false claims above came from reading the files instead of asking the tool.

**The defect that was real**, which neither claim found: `alembic upgrade head`
against an **empty** database genuinely did fail — but four revisions in, on
`ALTER TABLE comment_reactions`, because **only 8 of the 50 tables were ever
created by a migration**. The rest existed solely because
`Base.metadata.create_all()` ran at import time, and `--autogenerate` was then
run against databases that already had them — which is why five revisions titled
"add *X* table" contain nothing but `pass`. Against production, which had every
table, the history replayed fine, so this stayed invisible.

**Status: fixed in Phase 1** (2026-09-03, commit `316b86b`). `ghawy_baseline` is
now the root of the history and creates all 50 tables, verified equal to
production's `pg_dump --schema-only`. See
[`docs/ARCHITECTURE.md` §7](docs/ARCHITECTURE.md) and
[`docs/PHASE-1-REPORT.md`](docs/PHASE-1-REPORT.md).

---

## 🟡 Important Issues

### ✅ Issue 3 — Production CORS — FIXED

`backend/main.py:277` reads the allowlist from the environment:

```python
allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5500").split(",")
```

### ⏳ Issue 1 — N+1 queries — OPEN, scoped

Still to be swept properly. One correction to the original: the community
courses page is no longer an example — it previously called
`/courses/{id}/progress` once per course and now makes three parallel calls,
documented in the header of `frontend/src/js/courses.js`.
`admin.students_progress` is the reference for how these should be written.
Tracked as Phase 4.

### ⏳ Issue 2 — Native `alert()` / `confirm()` — OPEN, and smaller than stated

18 occurrences remain, not "أماكن كتير جداً":

| File | Count |
|---|---:|
| `src/js/team.js` | 9 |
| `teamdashboard.html` | 2 |
| `src/js/onboarding.js` | 2 |
| `src/js/ai-updates.js` | 2 |
| `course-detail.html` | 2 |
| `src/js/goh.js` | 1 |

The project convention is `showToast` and a custom confirm modal.

---

## 🟢 Minor Issues

### ✅ Issue 1 — Forbidden colour `#84cc16` — ALL BUT FIXED

The reported "more than 15 places" is now **2**, neither of which is site chrome:

* `src/js/goh.js:283` — a `ui-avatars.com` query parameter for a fallback avatar
* `src/js/whats-new.js:77` — one SVG fill in the what's-new illustration

### ⏳ Issue 2 — Skeleton loading / empty states — OPEN, unverified

Neither confirmed nor refuted in the 2026-09-03 pass. Needs a browser and a real
session to judge.

---

## ✅ What's Working Well — one correction

The original praise stands for router separation and the `services/` split. Two
entries need correcting:

* **"Auto Migrations (SQLite fallback)"** — there is no SQLite path. The
  application requires PostgreSQL: `app/database.py` raises at import unless
  `DATABASE_URL` starts with `postgresql`.
* **"Seeding: `seed_defaults` keeps the database always ready"** — this is the
  report's most consequential misreading. `seed_defaults()` running at import
  time is *why* half the schema has no migration, and it seeds **five real,
  named public figures** as platform guests with invented ratings and attendance
  numbers. It is a liability, not a strength. See `backend/main.py:52-90`.

---

## 📊 Summary — as of 2026-09-03

| | Original | Now |
|---|---:|---|
| Critical | 4 | **0** — 3 fixed, 1 never real |
| Important | 3 | 2 open (N+1 sweep, 18 native dialogs) |
| Minor | 2 | 1 open (skeletons), 1 all but closed |

Newly identified and **not** in the original report: 25 tables with no
migration; seeded real public figures; a third-party Supabase dependency polled
from the public landing page; secrets in git history, never rotated.
