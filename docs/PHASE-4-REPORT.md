# Phase 4 — Performance and request load

Everything below was measured before and after. Where a measurement contradicted
the plan, the measurement won — twice it reversed a decision, and once it caught
my own instrument lying to me.

---

## Headline numbers

| What | Before | After | How measured |
|---|---|---|---|
| Landing page, third-party requests (30s) | **19** | **0** | headless Chromium net-log |
| `GET /chat/channels/{id}/messages`, limit=50 | **56 queries** | **7** | SQLAlchemy query counter |
| `GET /chat/community/unread` (30s poll) | **15 queries** | **7** | same |
| `GET /dashboard/summary` (9 courses) | **31 queries** | **23** | same |
| Dashboard load → summary requests | **5** | **1** | `fetch` wrapped in-page via CDP |
| Dashboard load → total `/api/` calls | **22** | **17** | same |
| **Dashboard summary cost per load** | **5 × 31 = 155 queries** | **23** | combination of the two above |
| `messages` channel page (SQL) | 1056 µs | **73 µs** | `EXPLAIN ANALYZE`, 500 iters |
| `message_reads` receipts lookup | 6449 µs | **608 µs** | 500 iters |
| `chat_members` membership check | 358 µs | **32 µs** | 2000 iters |
| `notifications` bell poll | 276 µs | **34 µs** | 2000 iters |

---

## P-1 — The landing page polled a third party for something that fed nothing

Your reconnaissance said 18 requests/minute from two polls. Measured in a real
browser: **19 requests in 30 seconds, all from one poll**. `checkPurchases`
made *none* — its own guard, `if (document.querySelector('.progress-bar-fill'))`,
is never true, so neither its 5s interval nor its initial call ever ran.

The deeper finding is that the surviving poll fed nothing at all. Every element
the block touched is absent: `.progress-bar-fill`, `#livePurchaseText`,
`#initialBar`, `#initialSlotsFill` — absent from `index.html` (the only page
loading `main.js`), absent from the live page, and absent from **every commit in
this repo's history**. `git log -S` finds no commit that ever added that markup
anywhere. So `fetchLastPurchase` fetched a row every 10 seconds for
`updateLiveText` to write into an element that does not exist, while a second
1-second timer re-rendered the same nothing.

It could not have worked even with the markup. The newest row in that table is
**2026-07-01, 63 days ago**: the popup fires only when the row id changes, so it
could never fire, and the live text would have read "اشترى منذ ٦٣ يوم" — the
opposite of the social proof intended.

Removed. `main.js` now has **zero `setInterval` calls** and the landing page
makes no third-party polling requests at all.

**This turned into the most serious finding of the phase, and it is not a code
problem.** The block carried a hardcoded Supabase key. Deleting our copy does
not revoke it, and checking the actual premise rather than the key showed RLS is
not enforcing on that table at all:

```
GET    /rest/v1/purchases?select=*      → 200, 238 rows
DELETE /rest/v1/purchases?id=eq.-1      → 204
PATCH  /rest/v1/purchases?id=eq.-1      → 204
```

Both write probes used a filter matching no rows, and the count was 238 before
and after — nothing was altered. But `204` means the operation is *permitted*;
the same key with `?id=gt.0` empties the table. So it is not "238 first names
are readable", it is **anyone can destroy or forge the purchase record**, with a
key that is in git history permanently.

**This needs an owner action in the Supabase project — enable RLS. Revoking the
key does not fix it, and nothing in this repo can.** Logged as F-24.

---

## P-2 / P-3 — Two N+1s on the two most-polled chat endpoints

`GET /chat/channels/{id}/messages` ran `db.query(User)...first()` once per
message. The sibling endpoint `GET /chat/messages` has batched its senders for
some time — the pattern was already in the file, ten lines away. One query for
the distinct sender ids makes the cost flat instead of linear:

```
limit=20   27 → 8 queries
limit=50   56 → 7 queries
```

`GET /chat/community/unread` ran one COUNT per group channel **and** one per
forum slug — ten counts at today's shape — polled every 30 seconds from every
page that draws the sidebar badge. Each channel has its own `last_read_at`
cutoff, so a plain `GROUP BY` will not do; the cutoff is folded into the
predicate as one OR-arm per channel, which keeps a single grouped scan.

```
unread badge poll   15 → 7 queries
```

**Correctness is asserted, not assumed.** The benchmark recomputes the totals
with the naive per-channel loop being replaced and compares: total 468 = 468,
per-channel map identical.

---

## P-4 — Four indexes, and the measurement that nearly got two of them wrong

The live schema was read first (`pg_indexes`), not the models — the models are
not the authority, as Phase 1 established. That immediately removed two entries
from the candidate list: `user_progress(user_id)` is already covered by an
existing unique index on `(user_id, lesson_id)`, and the tables that mattered
carried nothing but their primary keys.

Then every candidate was benchmarked against a **restore of the production
database** (12,045 messages · 86,473 message_reads · 5,097 chat_members · 5,893
notifications).

**The single-run measurements were misleading and would have produced the wrong
answer.** `chat_members` looked like noise (0.40 ms vs 0.21 ms) and
`notifications` looked marginal enough to decline (0.80 ms vs 0.51 ms). Timed
over 2000 iterations, both are 8–11×. The loop is the measurement; one
`EXPLAIN ANALYZE` at this scale is not.

| Index | Query | Before | After |
|---|---|---|---|
| `messages(channel_id, created_at)` | channel page, LIMIT 50 | 1056 µs | 73 µs |
| | grouped unread poll | 3983 µs | 527 µs |
| `message_reads(message_id)` | 50-id receipts lookup | 6449 µs | 608 µs |
| `chat_members(channel_id, user_id)` + `(user_id)` | membership check | 358 µs | 32 µs |
| `notifications(user_id, created_at DESC)` | bell poll, LIMIT 20 | 276 µs | 34 µs |

Declined, with the number that argued against them:

- **`payments(user_id)`** — 91 µs → 29 µs. A real ratio on an already-cheap query that runs on dashboard and admin views, not in any polling loop. 1,488 rows. Not a bottleneck.
- **`user_progress(user_id)`** — already served by the existing unique index, 30 µs as it stands.
- **`messages(sender_id)`, `messages(is_deleted)`** — no hot query filters on them alone, and `is_deleted` is two-valued so an index would not pay for itself.

Shipped as migration `b7c3d9e1f204`, chained onto `d2e8a1f4c706` so the tree
keeps a single head. Verified from production state: the chain applies, all five
indexes appear, **every row count is unchanged**, downgrade removes exactly
those five, and re-upgrade restores them. Each builds in ~100 ms, so plain
`CREATE INDEX` keeps the migration transactional. `models.py` declares the same
indexes under the same names so the model and the schema stop drifting.

---

## P-5 — The dashboard, measured in the browser

Measured two ways. First from **production nginx logs of real users**: 5–6
`/api/dashboard/summary` requests within 6 seconds of a single dashboard load,
across four separate observed loads. Then in a browser, counting `fetch` calls
from inside the page.

`loadStatsCards` opened a `Promise.allSettled` of five requests —
`/courses/my?limit=100` plus **four byte-identical copies** of
`/dashboard/summary` — and used only the last one. `courseCount`, `achievCount`,
`streakData` and `xpData` were bound and never referenced. Two other functions
fetched the same endpoint again. All three now share one in-flight promise.

```
before   22 /api/ fetch calls,  5 × dashboard/summary,  1 × courses/my
after    17 /api/ fetch calls,  1 × dashboard/summary,  0 × courses/my
```

`/courses/my` **is not a route**. It fell through to `/courses/{course_id}`,
which tried to parse `"my"` as an integer — production logged **14 × 422** on it
in 90 minutes. It was not merely redundant, it was erroring on every dashboard
load, and nothing needed it: the list it counted is `dashData.courses`.

Then the endpoint itself: `/dashboard/summary` ran one COUNT per published
course, **31 → 23 queries** at 9 courses. Combined, a dashboard load costs 23
queries against this endpoint instead of 155.

---

## The rest of the N+1 sweep

You listed six locations as unread. All six were read.

| Location | Verdict |
|---|---|
| `dashboard.py:123` | **Real, and the hot one** — one COUNT per course. Fixed, 31 → 23. |
| `chat.py:459` | **Real** — one SELECT per message in mark-as-read, against the largest table, on every channel open. Batched. |
| `feedbacks.py:102` | **Real** — one User query per row. Batched. |
| `ws.py:110` | **Real, and provably dead work** — a per-channel "is this user a member" SELECT that could only ever return None, since the branch runs only for channels absent from the membership list loaded moments before. Removed. |
| `chat.py:935` | **False positive** — a single lookup, no loop. |
| `admin.py:1426/1436` | **Correct as written**, as you expected — grouped aggregates. Used as the reference. |

`admin.py:1338` also loops over all 1,916 users, but with no query inside it —
pure Python over pre-loaded maps. Already the right shape; left alone.

---

## Polling reviewed, and mostly left alone

- **`team.js` 4s** — justified, left. It is scoped to an active email-campaign send (`ecPollStatus`) and clears itself the moment the job reports `running: false`. Four seconds is right for a progress bar that stops on its own.
- **`utils.js` 30s notifications** — left. Already gated on `!document.hidden` with a `visibilitychange` handler, with a comment recording that hidden tabs used to hammer it. The index above cut its query cost 8×.
- **`dashboard-new.js` 30s online-count** — left. Costs **zero DB queries** (in-memory WS manager) and is already visibility-gated.
- **Landing page 5s/10s** — removed entirely (P-1).

---

## Stability review

- **`scheduler.py`** — every job already offloads via `asyncio.to_thread`. The Phase-era fix is holding.
- **Blocking I/O in async routes** — an AST scan for `requests`/`smtplib`/`urllib` calls inside `async def` routes found **none**. 25 uses of `run_in_threadpool`/`to_thread` across the app.
- **Unbounded result sets** — the `.all()` calls on large tables are `IN (ids)` batch loads bounded by the id list, plus three owner-only analytics endpoints over ~1,900 users. Not hot paths; left alone rather than optimised on speculation.

---

## Not done, and why

- **`/profile/me` is fetched 3× per page from `utils.js`** (measured, on all 13 pages). The same shared-promise fix applies — but the three call sites have **different side effects on failure**: one redirects to `/login` on 401, one calls `logout()` and handles 402 by redirecting to `/renewal`, one does nothing. Sharing a promise would give whichever ran first the deciding vote on auth behaviour, across 13 pages. That is a functional risk out of proportion to two saved requests, so it is proposed and stopped, per the standing rule. Logged as F-26.
- **`help_center.py:37`** — one query per support role, 4 total, on a low-traffic page. Measured, not slow, left alone.
- **F-23 avatar 429s** — untouched, as instructed. A dashboard load pulls **~95 avatar images**; that is the real cause, and the fix is a serving path or its own zone, never the global `api` zone. Still open for a later phase.

---

## Acceptance gate

- [x] **Request count and timing per page measured before and after, in the browser** — landing page (net-log) and dashboard (in-page `fetch` counter over CDP). Recorded above.
- [x] **Query count per hot endpoint measured before and after** — P-2 and P-3 specifically, plus `/dashboard/summary`, via `backend/scripts/bench_query_counts.py`.
- [x] **Every removed request has a written reason and proof what it fed still works** — the landing widget fed nothing (four absent elements, verified three ways); `/courses/my` was a 422; the four duplicate summaries were discarded results.
- [x] **Every index justified by an observed `EXPLAIN ANALYZE`, checked against the live schema first, shipped as a migration** — four kept with numbers, three declined with numbers.
- [x] **No behaviour change visible to a member** — `acceptance_security` 86/86, `acceptance_access_control` 32/32, `acceptance_team_roles` 64/64 throughout; unread totals asserted identical (468 = 468); dashboard rendered with 0 JS errors.
- [x] **The global rate-limit zone is unchanged** — `nginx/` was not touched in this phase.

## ⚠️ Deployment status — part of this phase IS live, and I did not deploy it

I planned to leave all of Phase 4 undeployed. That is not what happened. At
**08:49:53** the concurrent session ran a deploy, which rebuilt the image from
the working tree as it stood at that moment and ran `alembic upgrade head` on
startup. Verified by diffing the running container against this tree:

**Live in production now:**

| Change | How it got there |
|---|---|
| P-2 batched message senders | in the tree at 08:49, baked into the image |
| P-3 grouped unread counts | same |
| **All five indexes** (`b7c3d9e1f204`) | `alembic upgrade head` on container start |
| P-5 dashboard-new.js (5 summary calls → 1) | frontend is bind-mounted, live on save |
| P-1 landing page (polling removed) | bind-mounted, live on save |

**Still undeployed** (committed after 08:49):

- `dashboard.py` grouped course counts — production still runs the per-course COUNT loop (confirmed at line 123 of the live file)
- `feedbacks.py` batching
- `chat.py` batched read-receipts
- `ws.py` redundant-query removal

So production currently has a *partial* Phase 4. Nothing is broken by that —
every piece is independent, and the acceptance suites passed at each step — but
it is not the clean "deploy in a quiet window" you asked for, and the index
migration reached production without the review you intended. `alembic current`
is `b7c3d9e1f204`, single head, all row counts unchanged.

**The remaining four changes still need a deploy.** They are backend-only, so
they need a rebuild; there is no migration left to run.

And one thing that is not a deploy at all: the Supabase RLS problem in P-1 is
live right now, it allows anonymous DELETE and PATCH, and only you can close it.

---

## Two things about how this phase ran

**A concurrent session is committing to this repo.** Partway through, my
in-progress `dashboard-new.js` edit was swept into another session's
`git add -A` and committed under its own message (`597e829`), my scratch
database was dropped and replaced, and a new migration (`d2e8a1f4c706`) appeared
in the tree. None of it was harmful — the commit message was accurate and the
`/courses/my` 422 finding in it is a genuine catch I had missed — but it means
`git show HEAD:<file>` was returning my *new* code as the "before", and several
of my early measurements were invalid until I noticed. My index migration is
chained onto their head so the tree keeps one head.

**My own instrument lied to me twice.** The first browser comparison used a
persistent Chrome profile, so the "before" run was served my new JavaScript from
cache; and the first `/dashboard/summary` benchmark reported the fix making
things *worse* (20 → 21 queries) because the fixture contained no courses, so it
measured the added grouped query and none of the saving. Both were caught by the
numbers not making sense, not by the code looking wrong.
