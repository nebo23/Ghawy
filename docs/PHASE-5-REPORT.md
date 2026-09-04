# Phase 5 — Cleanup and Dependencies

Executed 2026-09-04 against `master`, on the production host, with the three
containers serving real users throughout.

**Total removed: 1,134,221 bytes from the tracked tree** (53,557,469 →
52,423,248), plus **46 MB from the backend image** (570 MB → 524 MB).

---

## 0. The rule this phase ran on

> "No grep hits" is not evidence of unused. The evidence is that the caller is
> gone.

Every deletion below carries that evidence. Two findings are the rule earning
its keep: `boto3` qualified because its calling file was deleted in May and the
history says so (§5), and the eight "unused" dependencies a naive scan flags
were all confirmed load-bearing and left alone.

Two measurements in the brief were overturned, and one of my own was wrong and
was caught by verification rather than by reading. All three are recorded.

## 1. What verification actually existed this time

`BASELINE.md` recorded three gaps: no browser on the host, therefore no
screenshots, no console errors, and no authenticated page behaviour. All three
are now closed. Chrome was already cached at
`/root/.cache/puppeteer/chrome/linux-150.0.7871.24/`; with `playwright-core` and
a minted admin JWT, the acceptance gates below are measured in a real browser
against the live site, logged in.

Three harnesses, all in the session scratchpad:

| Harness | What it measures |
|---|---|
| `verify.js` | all 31 pages: console errors, page errors, failed requests, and whether every `fa-` class on the page renders a glyph |
| `ab.js` | serves the *pre-change* stylesheets by request interception and diffs `getComputedStyle` against the live ones — a true A/B on one running site |
| `oc.js` | functional check that the consolidated online-count still paints |

`ab.js` is the one that mattered: it caught a regression I had introduced and
would not have found by reading (§3).

---

## P5-1 — Dead files  (commit `34a8890`)

| File | Bytes | Classification | Evidence |
|---|---:|---|---|
| `frontend/src/js/dashboard.js` | 18,152 | `UNUSED` | no `<script src>` on any of the 31 pages; no dynamic `import()` in the tree; the only two runtime-built `<script>` tags (`course-details.html:320`, `faq.js:221`) are JSON-LD blocks with no `src`; **0 requests in 43 h of production nginx logs**, against 123 for the FontAwesome woff2 files in the same window |
| `frontend/src/js/recorder.js` | 3,803 | `UNUSED` | same searches; **0 requests in the same 43 h** |
| `Requirements.txt` (root) | 322 | `LEGACY` | `backend/Dockerfile:13` copies `requirements.txt` from a build context of `./backend`, so it resolves to the backend file. This one lists 15 packages against the backend's 61 and is missing `apscheduler`, `gunicorn`, `authlib`, `pillow`, `weasyprint`, `requests`, `starlette`, `tzdata`, `email-validator`, `itsdangerous` — installing it produces an app that cannot start |

The log evidence is the point: it is not that nobody searched, it is that in 43
hours of real traffic nobody loaded them.

## P5-2 — FontAwesome  (commit `98d60cf`)  −1,111,158 B

The brief framed a trade: retreat 6 pages to 6.5.0 for 328 KB, or advance 18
pages to 7.0.0 for 1.1 MB plus an icon audit. Measuring first collapsed it.

**The icon audit.** Every `fa-` token on the 18 pages *and* on every JS/CSS
asset they load — so dynamically applied classes are included — resolved
against both stylesheets. 6.5.0 defines 2,515 `fa-` selectors, 7.0.0 defines
2,580. Exactly one used token fails in 7.0.0: `fa-sparkles`
(`dashboard-new.js:406`). It fails in 6.5.0 too, because it is a FontAwesome
**Pro** icon — it renders nothing today, on 12 pages. So there were **zero real
blockers**, and the larger saving was also the cheaper one. The legacy
`fas`/`far`/`fab` short classes are defined identically by both majors and used
by neither.

**What an unaudited swap would have broken.** Two rules name a font family as a
literal string, where no `fa-` class appears and no icon audit would look:

* `community.css:1156` — `.sh-faq-summary::after`, `content:'\f078'`, chat + DMs
* `main.css:6888` — `.tr-card-cta::after`, `content:'\f177'`, tracks + courses

`main.css` already hedged with both names, so someone had hit this before.
Both now name 7.0.0 only; both codepoints exist there (`fa-chevron-down`,
`fa-long-arrow-left`).

**Why 7.0.0 is a third of the size:** 6.5.0 shipped `.ttf` *and* `.woff2` — 705
KB of its 1.1 MB was the ttf set. 43 h of logs record **2** `.ttf` requests
against **123** woff2. FontAwesome dropped ttf in v7 themselves.

**Verified:** 537 distinct `fa-` icon classes across all 31 pages, **0** whose
`::before` renders no glyph; no new console error or failed request.

## P5-3 — The 63 CSS collisions  (commit `014f3ad`)

The brief was right that `dashboard.css` cannot be deleted. The reason is
sharper than "the new file does not supersede the old": **the two files serve
disjoint page sets.** `dashboard-new.css` is never loaded without
`dashboard.css` (13 pages load both, always in that order), and
`teamdashboard.html` loads `dashboard.css` alone. For any selector teamdashboard
uses, the `dashboard.css` copy is the only one that renders there.

63 colliding (at-rule context + selector) pairs — the brief's number,
reproduced independently. Classified by whether a loser exists at all:

| # | Situation | Action |
|---:|---|---|
| 8 | identical body, selector used on teamdashboard | dropped the **new** copy |
| 2 | identical body, selector absent from teamdashboard | dropped the **old** copy |
| 16 | bodies differ, absent from teamdashboard, new wins by order | dropped the **old** copy |
| 4 | **old** wins via `!important` | **kept** |
| 33 | bodies differ, both load-bearing on their own page set | **kept** |

**63 → 37.** Only 26 had a loser to delete. The other 37 are deliberate, and
that is the finding: the brief's "keep one, delete the loser" holds for 26 of
63, not for all of them.

The 4 `!important` cases are not accidents. They are the block labelled
`BLUE + WHITE REDESIGN OVERRIDES` (`dashboard.css:1452`) plus the light-theme
layer — including the documented `h2, h3, .section-header` rule. They exist to
re-skin the older gold design to blue. Deleting them reverts the member area.

### Two traps, both caught by measuring

**The cascade is per-property.** Nine of the 16 "overridden" old rules declared
properties the winning rule does not, so those declarations were still
applying — the two designs were blended, not replaced. Four
(`.sb-combined-card`, `.sb-streak-card`, `.sb-level-title`, `.sb-xp-text`)
matched **no element on any page** and were simply dead. The rest were folded
into the winning rule before the loser was removed.

**"Identical body" does not imply "safe to delete" — I got this wrong.** In
`dashboard-new.css` the `@768 .notif-panel` rule physically precedes the base
rule, which made the `@640` copy the last `width` declaration at ≤640px.
Removing it as a duplicate widened the notification panel from **358px to
374px on 11 pages at 390px wide**. The A/B harness caught it; reading the two
rule bodies never would have. It is restored, with a comment saying why it
stays. I made the same class of error on `@768 .dash-grid-side` and reverted
that fold before it shipped.

**Verified:** pre-change stylesheets served by request interception, diffed
against live — **14 pages × 3 viewports (1440×900, 900×1000, 390×844), 1,482
selector snapshots, 24 properties each: zero differences.** Brace balance equal
before and after in both files, and in every stylesheet touched.

## P5-4 — Remaining duplicates  (commit `92c4849`)

`fetchOnlineCount` had 4 copies; P5-1 took one, leaving 3. They are **not** the
same function: the chat pages call `apiFetch()` and paint the presence pill,
`dashboard-new.js` calls `api()` and paints `#dashOnlineCount`. The helpers
differ where it matters — `api()` redirects an expired subscription to
`/renewal` on a 402, `apiFetch()` only handles 401. Hoisting the request into
`utils.js` with a bare `fetch()` would have silently dropped that redirect.

`window.getOnlineCount(fetcher)` in `utils.js` therefore takes the caller's
helper, does the request, and returns the number — or `null` on any failure,
which every caller reads as "leave the count alone", so a failed poll can never
blank a correct number. Each page keeps its own painter, the part that genuinely
differs. Verified live: all three pages fire the request and paint `25`.

`?v=` bumped for `utils.js` (26 pages) and `dashboard-new.js` (12) — a new
`utils.js` global behind a stale cache-bust is exactly what has blanked chat and
DMs before.

**The API base: 5 definitions, not 3.** `utils.js`, `main.js` and `renewal.js`
declare a global `const API`; `catalog.js` and `course-card.js` keep a
closure-local `API_BASE`. They **cannot** collapse into `utils.js` as things
stand: `index.html` loads `main.js` and `catalog.js` *without* `utils.js`, and
`renewal.html` loads `renewal.js` without it. Pulling `utils.js` onto those
pages would run auth guards and polling on public pages. Left alone,
deliberately. (The three globals never co-load — if they did it would be a
`SyntaxError`, not a subtle bug.)

## P5-5 — Dependencies  (commit `8cf7833`)  −46 MB image

Eight of the nine no-direct-import requirements are indirect and were **kept**:
`uvicorn`, `gunicorn`, `psycopg2-binary`, `python-multipart`, `tzdata`,
`itsdangerous`, `websockets`, `email-validator`. All eight were confirmed to
import in the rebuilt image. A naive scan flags every one.

The ninth, `boto3`, qualified on the phase's own standard — the caller is gone,
and git says when:

* `4843216` (2026-05-29) added `backend/app/services/cloudflare_r2.py`, a
  Cloudflare R2 client on `boto3` + `botocore.config`
* `2f8d8c8` (2026-05-31) deleted that file

`boto3` has never appeared in any other `.py` file in the history. Uploads are
written to local disk by `file_service.save_upload` via `aiofiles`; there is no
S3 client, no bucket, and no R2/S3 variable in `.env.production`. `botocore` was
the largest single item in the image at 27 MB.

**Verified:** image 570 → 524 MB; `main:app` imports with all 262 routes;
production restarted onto the new image and is healthy; `alembic current` ==
`heads` (`d1e4f7a2b9c3`); a real upload through `POST /chat/upload` wrote and
served correctly (test file removed afterwards); and `requirements.txt` installs
clean from scratch on a bare `python:3.11-slim` (exit 0).

## P5-6 — `admin-course-detail.html` stays `UNKNOWN`

The brief's test was: zero traffic over a meaningful window qualifies it,
otherwise it stays. **It is not zero.** 43 hours of nginx logs show 5 page loads
plus its CSS/JS.

But the logs also answer *what opened it*, which is more useful than the count:
every hit is from **one IP**, and the first arrives with
`Referer: https://ghawy.ai/robots.txt`. `robots.txt:24` carries
`Disallow: /admin-course-detail` — which publishes the URL to anyone who reads
the file. The visitor then browsed `/renewal`, `/register`, `/chat` and
`/privacy` collecting `402`s, and the page's own call went to
`/api/courses/admin/null` (404) because it was opened with no `?id=`. That is
someone who found the URL in `robots.txt`, not an admin doing work.

So: no admin use observed in 43 h, but non-zero traffic and a plausible
bookmark. **It stays, and the finding stays open.** The only place the answer
exists is with the owner.

---

## Also in scope

**Unused CSS/JS via coverage tooling.** Measured with Chrome's CSS coverage
across all 31 pages. Reporting the numbers and proving nothing from them:

| Stylesheet | Bytes | Max covered on any one page |
|---|---:|---:|
| `main.css` | 221,826 | 24.8% |
| `team.css` | 92,704 | 4.1% |
| `dashboard.css` | 74,484 | 21.4% |
| `dashboard-new.css` | 66,487 | 35.8% |
| `community.css` | 42,052 | 3.8% |

These are **not** dead-code figures. Coverage records what a default page load
paints in about three seconds, and this app is heavily state-dependent:
`team.css` styles a tabbed dashboard where one tab renders, `community.css`
styles a chat where one channel renders, and modals, drawers and the light theme
never open at all. A union across states would be needed before any of this
justified a deletion, and even then it would miss error and empty states. As the
brief predicted, this is the least conclusive item; **nothing was deleted on
coverage evidence.**

**Scripts loaded on pages that do not need them.** `dashboard-new.js` is loaded
by **12** pages, not 13 — `help-center.html` mentions it only in two comments
and reimplements the helpers inline. All 12 loaders contain DOM anchors the
script drives; the thinnest (`teamdashboard.html`) still gets its notification
panel from it. **No load is gratuitous; nothing removed.**

**Comments.** Left alone, per the brief — the comments here document real
decisions. The one removal was a comment-adjacent fallback made false by this
phase: `"Font Awesome 6 Free"` in `community.css` and `main.css` now names a
family that no longer ships.

---

## Acceptance gate

| Gate | Result |
|---|---|
| Every deleted file has a classification and evidence | §P5-1, §P5-2, §P5-5 above |
| Nothing classified `UNKNOWN` was deleted | `admin-course-detail.html`, `admin-courses.js/.css`, `docker-compose.test.yml`, `backend/docker-compose.yml`, `.env.production.bak.*` all untouched |
| All 31 pages open; no 404 on any asset | 31/31 → 200; 53 distinct local assets → 200, zero 404 |
| No new console errors vs `BASELINE.md` | 31 pages in a logged-in browser: **zero** new errors, **zero** new failed requests |
| CSS brace balance on every stylesheet touched | equal before and after: `dashboard.css` 580→561, `dashboard-new.css` 427→421, `community.css` 291, `main.css` 1440 |
| FontAwesome decision justified by measurement; every `fa-` class resolves | 2,515 vs 2,580 selectors audited; 537 icon classes probed live, **0** unresolved |
| The 63 collisions resolved deliberately, not by deleting a file | 26 resolved, 37 kept with reasons; both files still exist |
| `boto3` removed, image rebuilt, app boots, uploads work | 570→524 MB; healthy; migrations at head; upload written and served |
| Dependencies install clean from scratch | `pip install -r requirements.txt` on bare `python:3.11-slim`, exit 0 |

## Findings raised, not fixed

1. **`build-with-me.html` throws `SyntaxError: Identifier 'token' has already
   been declared`** — two scripts declare `const token` at global scope. The
   same collision class as the `ws` bug that once killed chat pages.
2. **`build-with-me.html` opens a WebSocket to `wss://ghawy.ai/api/live-sessions/ws`,
   which 404s.** This is the `live.py` "legacy" WS that Phase 0 flagged
   `UNKNOWN`; the client still calls it and the server no longer answers.
3. **`register.html` throws `TypeError: Cannot set properties of null (setting
   'innerText')`** on load.
4. **`fa-sparkles` renders nothing** (`dashboard-new.js:406`) — a Pro icon on a
   Free licence, blank on 12 pages.
5. **`.course-card:hover` gold border.** `dashboard.css`'s legacy
   `border-color: var(--gold-border)` outranks the new card's transparent
   gradient border by specificity, so the redesigned hover effect is defeated by
   the old design. Preserved exactly in P5-3 because changing it is a visual
   design decision, not a cleanup. Recommend dropping the folded declaration.
6. **`admin-course-detail.html` has no `?v=` on `dashboard.css`** — the only
   page without one, so it serves whatever nginx cached for up to 7 days. Not
   touched because the page is `UNKNOWN`.
7. **`robots.txt` publishes `/admin-course-detail`** — `Disallow` advertises a
   URL to anyone who reads the file, and the logs show that is exactly how its
   only visitor found it.
8. **`apiFetch` has 7 definitions** (`chat.html`, `direct-messages.html`,
   `course-detail.html`, `courses.js`, `profile.js`, `admin-courses.js`,
   `goh.js`) plus `api()` in `dashboard-new.js` — a larger duplication than
   anything in P5-4, and one that overlaps the unapproved Phase 6.
9. **`teamdashboard.html` loads Chart.js from `cdn.jsdelivr.net`** — the only
   remaining runtime CDN dependency in the member area, in a codebase that
   self-hosts its icon libraries precisely because a CDN dependency once made
   icons vanish.

## Phase 6

Not started. Unifying `chat.html` and `direct-messages.html` is a separate
decision and is left as one.
