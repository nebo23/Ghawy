# Arabic signup — hardening

> **Note on this file.** The earlier sections (§1–§4) were not in the repository,
> in git history, or anywhere on the production host when this addendum was
> written — only the addendum text itself was supplied. The file therefore starts
> at §5. Where §5 refers to "§3" and "§4's table" it means the note the owner was
> working from; the §4 additions are reproduced in full below with their results,
> so this file stands on its own.

---

## §5 — Addendum to §3: the Google name is replaced, not kept alongside

The owner's confirmation of §3, and a tightening of it.

**The rule, in his words:** for a Google signup, once they register and pay, the
Arabic name they type *is* the name. The Latin one Google supplied is treated as
if it never existed. Everything about a member's name is Arabic — and a
half-Arabic, half-Latin name is not allowed anywhere, at any door.

Status: **closed.** Two of the three places listed below are fixed, the third is
reported and deliberately untouched, and a fourth door — found by carrying out
the verification §3 asked for — is fixed. Live on production 2026-09-06.

Commits: `e74ad99` (the two places), `0f23b3c` (the fourth door).

---

### 5.1 What was already correct — verified, not rebuilt

| Claim | Verdict | Evidence |
| --- | --- | --- |
| `complete_onboarding` writes `full_name` and `first_name`/`last_name` from what the member typed; the Google name is overwritten in `users`, not kept in a second column | holds | `profile.py:396-400`; acceptance `[G4]`, `[G4b]` |
| `is_arabic_name` requires every letter to be Arabic, so `Mohamed محمد` and `محمد Salah` are both rejected | holds, at both doors | acceptance `[1a]`, `[1g]`, `[1h]`, `[G3b]`, `[G3c]`; live `POST` returns 422 for all three shapes |
| Once the name is Arabic, `profile.py`'s ratchet stops it going back to Latin | holds | acceptance `[5c]`, `[5d]`, `[R]` |
| A Google member cannot reach the community carrying the Latin name, because `utils.js:292` bounces `onboarding_completed = false` back to onboarding | **did not hold** | see §5.5 |

The last row is the reason §3 said *confirm this rather than assume it*. The
bounce itself works. What did not hold is the assumption that the flag it reads
could only be raised by the door that enforces the name rule.

---

### 5.2 Place 1 — the browser kept the old name after onboarding *(fixed)*

`onboarding.js` synced only `onboarding_completed` into `localStorage['user']`
after a successful submit. `full_name` was never refreshed, so the member typed
`محمد صلاح`, the row was correct, and the cached copy still said `Mohamed Salah`
until they logged out and back in. `course-detail.html:3549` reads that copy as
the certificate name — the worst place for it to surface.

**Fixed.** `POST /profile/complete-onboarding` now returns `full_name`,
`first_name` and `last_name`, and the sync block writes all three. The values
come from the stored row rather than from what was submitted, because
`clean_display_name` may have altered it and `split_full_name` is the only thing
that knows where a compound first name ends (`عبد الرحمن علي` → `عبد الرحمن` +
`علي`); the browser has no copy of that map.

Proved by A/B on the live site — same flow, same backend, only `onboarding.js`
differing, with `/profile/me` suppressed so nothing else could repair the cache:

| | cached `full_name` after onboarding | `first_name` / `last_name` |
| --- | --- | --- |
| before | `Nabil Ahmed` | `Nabil` / `Ahmed` |
| after | `نبيل أحمد` | `نبيل` / `أحمد` |

Both runs reached `dashboard.html` with `onboarding_completed: true`, so the
difference is the name and nothing else.

**One qualification worth recording.** In an unsuppressed run the stale value
often repairs itself within seconds: any page's auth guard re-fetches
`/profile/me` and overwrites the cached object wholesale. So the original bug
was a race rather than a permanent wrong name — but a race is exactly what a
synchronous read loses. `course-detail.html` draws the certificate from the
cache when `currentUserData` has not arrived, and that read does not wait.

---

### 5.3 Place 2 — the prefill offered a mixed name *(fixed)*

`_arabic_name_suggestion` arabized the first token and kept the surname as it
was, so `Mohamed Salah` was suggested as `محمد Salah`. Two problems, and the
second is the one that mattered: it is a default value the form's own rule
rejects, and it demonstrates the shape the owner has just said must never exist.

**Fixed.** Every token is arabized now, with three outcomes and no fourth:

| stored name | suggestion |
| --- | --- |
| both tokens resolve | the whole Arabic name — `Nabil Ahmed` → `نبيل أحمد` |
| only the first resolves | the Arabic first name alone — `Mohamed Elsayed` → `محمد` |
| neither resolves | `""` — no prefill at all |

It can no longer emit both scripts in one string. Checked exhaustively over 100
name combinations drawn from the map and from names outside it: zero mixed-script
suggestions (acceptance `[G2b]`).

The logic moved to `services/name_utils.py`, beside the map it reads and beside
`is_arabic_name`, which is the rule that judges its output — the suggestion and
the rule that must accept it now live in one file.

The owner's own test account is `Nabil Ahmed`, so the case he will check first
comes back fully Arabic. Confirmed against the live endpoint:

```
GET /profile/onboarding-status
{"onboarding_completed":false,"needs_arabic_name":true,
 "suggested_name":"نبيل أحمد","current_name":"Nabil Ahmed"}
```

**On splitting the onboarding field into first and last:** not done, and it is
no longer needed. That suggestion existed so the form could fill one field and
leave the other blank rather than offering a half-filled sentence. With the
one-word outcome above, the single field does exactly that — it comes up holding
`محمد` and the member types one more word. Splitting it would be a UI change the
rule does not require.

---

### 5.4 Place 3 — `legacy_emails.full_name` *(reported, not changed)*

Out of scope for this pass, as instructed. The numbers, from production:

| | rows |
| --- | --- |
| total roster rows | 492 |
| with a name at all | 451 |
| containing a Latin letter | **447** |
| containing an Arabic letter | 5 |
| containing both scripts | 1 |

**Yes, a campaign path reads that column.** `GET /email-campaigns/atlas-recipients`
(`email_campaigns.py:306-311`) queries `LegacyEmail`, searches on `full_name`,
and builds each recipient from it. Two branches:

- roster address **with** a platform account → `row["name"] = u.full_name or r.full_name` — the account's own name wins, so the Arabic rule governs it.
- roster address **without** an account → `row["name"] = r.full_name` — the raw Latin roster name, and `row["name_ar"] = arabize_first_name(...)`, which is Arabic-or-empty.

**196 roster rows have a Latin name and no platform account.** For those, a
campaign that uses `{name}` addresses the person in Latin; one that uses the
Arabic first-name variable gets Arabic or nothing. This is the one remaining
place a Latin name reaches a member, and it is worth deciding about deliberately
rather than meeting it later.

---

### 5.5 Place 4 — the flag had a second door *(found by §5.1's check; fixed)*

§3 said to confirm that `utils.js`'s bounce closes the window. It does not,
because a second endpoint set the flag it reads with no check of any kind:

```python
@app.patch("/users/me/complete-onboarding")      # main.py, before
def complete_onboarding_patch(current_user = Depends(get_current_user), ...):
    current_user.onboarding_completed = True
```

Demonstrated against the live site with one member's own token:

```
POST  /profile/complete-onboarding  {"full_name":"Nabil Ahmed"}  ->  422  اكتب اسمك بالعربي 🙏
PATCH /users/me/complete-onboarding                              ->  200
row after: Nabil Ahmed | latin_name_ok=f | onboarding_completed=t
```

The door that refuses is worth only as much as the other door that sets the same
field. A Google signup could decline the question entirely and walk in under the
Latin name.

**Fixed.** The PATCH now asks `needs_arabic_name` — the same predicate the step
itself uses, imported rather than restated, since a second copy of a condition is
how one door comes to allow what the other refuses. Nothing changes for a member
who is not being asked: an Arabic name, or a recorded «اسمي مش بالعربي», passes
exactly as before, and `onboarding.js` only reaches this call after the POST has
already settled the name. Re-checked live after deploy:

```
PATCH /users/me/complete-onboarding  ->  422  اكتب اسمك بالعربي 🙏   (flag stays false)
POST  with a real Arabic name        ->  200
PATCH now                            ->  200
```

This is the "one field, many doors" shape from the permission-bypass notes,
applied to a rule rather than a permission.

---

### §4 additions — proved at the endpoint

| Case | Endpoint | Expected | Result |
| --- | --- | --- | --- |
| `محمد Salah` as the onboarding name | `POST /profile/complete-onboarding` | 422 | **422 live** + acceptance `[G3b]` |
| `Mohamed محمد` as the onboarding name | same | 422 | **422 live** + acceptance `[G3c]` |
| `محمد` + `Salah` in the two signup fields | `POST /auth/register` | 422 | acceptance `[1g]` — see note |
| `Mohamed` + `صلاح` in the two signup fields | same | 422 | acceptance `[1h]` — see note |
| a valid Arabic name at onboarding | `POST /profile/complete-onboarding` | 200, all three columns Arabic | **200 live**, row `نبيل أحمد` / `نبيل` / `أحمد`; acceptance `[G4]`, `[G4b]` |
| the response carries the name back for the cache | same | present | acceptance `[G4c]` |
| the flag cannot be raised while an Arabic name is owed | `PATCH /users/me/complete-onboarding` | 422 | **422 live** + acceptance `[F1]`–`[F4]` |

**Note on the two `/auth/register` rows.** They cannot be proved against the live
endpoint: Turnstile is enforcing and sits *ahead* of the name check, so every
live attempt returns `403 Please complete the 'I'm not a robot' verification`
and never reaches the rule. They are proved in
`backend/scripts/acceptance_arabic_names.py`, which stubs Turnstile and nothing
else — the script's own docstring gives that as the reason it stubs it. Register
checks each field separately (`is_arabic_name(first) and is_arabic_name(last)`),
which is why one Arabic field and one Latin field is refused.

Full suite: **41 checks, 41 passing**, against a throwaway database.

```bash
DATABASE_URL=postgresql://.../ghawy_scratch python backend/scripts/acceptance_arabic_names.py
```

---

### Verified in a real browser

Headless Chrome against `https://ghawy.ai`, driving a purpose-made member shaped
like a Google signup (`Nabil Ahmed`, paid, `onboarding_completed = false`).

- the name field comes up holding `نبيل أحمد`, RTL, with «اسمي مش بالعربي» beneath it
- typing `محمد Salah` outlines the field and shows «اكتب اسمك بالعربي 🙏»; the step will not advance
- completing with `نبيل أحمد` stores `نبيل أحمد` / `نبيل` / `أحمد` and lands on the dashboard
- `localStorage['user']` holds the Arabic name **immediately**, with no logout — this is the check that catches §5.2, and the one most likely to be skipped
- dashboard, profile, profile-settings and chat show no Latin form of the member's name
- the backend addresses them as `نبيل أحمد` → first name `نبيل`, `resolves_to_arabic = True`, so campaign and email greetings are Arabic

**The phone/OTP step was skipped** — it sends a real SMS. Everything after it ran
for real against production.

**On the Latin names still visible in chat:** the read-receipt tooltips do show
`Nabil Ahmed`, and it is not this member. There are several long-standing
accounts under that exact name (ids 5, 836, 2962), plus `omar nabil`,
`Ahmed Shaban` and others. Those are the existing Latin names the owner decided
never to convert. Since the rule shipped (2026-09-06 09:38) no member has
completed onboarding under a Latin name without the explicit opt-out: five
Latin-named signups since then are all still `onboarding_completed = false` and
will be asked; the one completed Latin name has `latin_name_ok = true`.

The test account was deleted afterwards, scoped to that one user — 4
`chat_members`, 4 `message_reads`, 1 `message`, 1 `users` row. Community counts
unchanged: 1,502 channels, 5,215 memberships, 1,957 users.

---

### One unrelated sharp edge, noted in passing

`users.badge` is nullable with no database default, and `GET /profile/me` 500s on
a NULL (`ResponseValidationError: 'badge' should be a valid string`). **No real
member is affected** — all 1,957 rows have `Member`, because registration sets
it. It only surfaced because the test row was inserted directly. Worth a default
on the column if rows are ever created outside the app again.

---

## §6 — The opt-out is removed: Arabic, no exceptions

Owner, 2026-09-06, after §5 shipped: **«شيل الـ اسمي مش بالعربي دي وشيلها برضو
في الـ onboarding — انا عايز كل حاجة تبقي بالعربي»**, plus *add a notice on the
signup form that the name must be in Arabic*, and *confirm the Arabic name is
what lands in the team dashboard — but a Google signup who hasn't paid can stay
in English, because they haven't paid.*

This reverses the earlier decision recorded in §2 (Arabic **with** an opt-out).
Status: **live on production**, commit `2ed735d`.

### What it cost

Almost nothing, which is worth knowing before worrying about it:

| | |
| --- | --- |
| members who ever ticked «اسمي مش بالعربي» | **1** |
| of those, still mid-onboarding | 0 |
| active members mid-onboarding with a Latin name (now required to write Arabic) | 5 |

The original fear behind the opt-out — locking out the ~12 members who
genuinely cannot write their name in Arabic — did not materialise, because
essentially nobody used it.

### Removed from

| surface | what went |
| --- | --- |
| `register.html` + `register.js` | the checkbox, its reveal-on-failure, and `latin_name_ok` in the POST body |
| `index.html` signup modal | the same, inline |
| `onboarding.html` + `onboarding.js` | the checkbox and the whole `latinNameOk` branch |
| `schemas.py` | `UserRegister.latin_name_ok`, `OnboardingUpdate.latin_name_ok` |
| `users.py`, `atlas.py` | the exemption and both writes of the column |
| `profile.py` | the opt-out branch; `needs_arabic_name` is now the name alone |

An older cached client that still posts `latin_name_ok` is **not** humoured —
the field is gone from the schemas, pydantic drops it, and the name is judged on
its own. Checks `[1e]`, `[3b]`, `[G6]` and `[F3]` exist precisely to prove that,
because a flag nobody reads looks exactly like a flag that still works until
something tests it.

**The column stays on `users`.** Nothing writes it, nothing reads it in a
decision. It is the record of the one account created while the opt-out existed;
dropping it would erase that and buy nothing.

### A hole closed on the way

`complete_onboarding` used to finish even when no name was sent at all. That was
harmless only while «اسمي مش بالعربي» was a legitimate second answer. With no
second answer left it was the same back door as the ungated PATCH in §5.5, so it
now refuses (`[G7b]`). The page's field is `required` and the message says what
to do; nobody is locked out of their account, they land back on the same step.

### Two things deliberately unchanged

**The profile ratchet.** `PUT /profile/me` still enforces Arabic only when the
stored name is already Arabic. A plain rule there would reject the bio save of
every one of the 1,683 Latin-named members, for a field they never touched. The
hard rule is on *new* names. `[R]`, `[5b]`, `[5c]` pin it.

**The admin door still warns rather than blocks.** It is the owner's own tool
for adding someone by hand, sometimes a guest who has no Arabic name. It returns
`name_warning` and creates the account (`[4a]`–`[4c]`).

### Unpaid Google signups stay in English — verified

The step sits behind `get_current_active_member`, so nobody asks them, nothing
renames them, nothing blocks them. They are asked the first time they pay and
land in onboarding. `[G9]`/`[G9b]` pin it, and it was checked live against two
accounts built the way `google_auth.py` builds one:

```
paid   (is_active=true)  GET /profile/onboarding-status
  → {"needs_arabic_name":true,"suggested_name":"يوسف عماد","current_name":"Youssef Emad"}
unpaid (is_active=false) GET /profile/onboarding-status
  → 402  حسابك غير مفعل — يرجى تجديد الاشتراك
POST /profile/complete-onboarding as the unpaid member → 402, name unchanged
```

### The Arabic name reaches the team dashboard — verified

The paid Google account was driven through onboarding in a real browser: the
opt-out checkbox is gone from the page, the field came up holding `يوسف عماد`,
and the member typed their own name. Then, signed in as the owner, the team
dashboard's Members tab was searched for both accounts:

| | team dashboard shows | source |
| --- | --- | --- |
| paid, completed onboarding | `يوسف عماد` | `GET /admin/users` → `users.full_name` |
| unpaid, never asked | `Karim Fathy` | same |

`team.js:349` renders `user.full_name`, which is the column `complete_onboarding`
writes — so nothing extra was needed to make the Arabic name land there; it was
confirmed rather than built.

### The notice on the signup form

Both signup surfaces now carry it up front, above the fold, in both languages:

> مهم: اكتب اسمك بالعربي — ده الاسم اللي هيظهر في شهاداتك وفي رسايلنا ليك.
> *Important: write your name in Arabic — this is the name on your certificates
> and in our messages to you.*

It replaces a checkbox that only appeared **after** the rule had already fired.
A refusal reaches the member once they have typed their name; the notice reaches
them before. (Use an icon from the free FontAwesome set — `fa-regular
fa-circle-info` is Pro-only and renders as an empty box.)

Full suite after this change: **45 checks, 45 passing.** Test accounts deleted
afterwards, scoped by user; community counts unchanged at 1,502 / 5,215 / 1,957.
