"""Acceptance checks for the Arabic-name rule on new members.

Runs against a throwaway DB, same shape as the other scripts here:

    DATABASE_URL=postgresql://...:5432/ghawy_scratch \
        python backend/scripts/acceptance_arabic_names.py

What the owner decided, and what is therefore checked:

  * Arabic is required from NEW members, with NO opt-out. «اسمي مش بالعربي»
    existed until 2026-09-06 and was removed at the owner's request: every
    door that creates an account now refuses a name that is not written in
    Arabic. The old `latin_name_ok` flag is no longer read by anything, so
    sending it changes nothing — several checks below exist to prove exactly
    that, because a flag that is ignored looks identical to a flag that works
    until somebody tests it.
  * No existing name changes. Not by script, not by migration, not by prompt.
    [N] below is the one that proves it: every stored name is compared before
    and after the whole run.

The doors are checked one by one because they enforce differently on purpose:
the signup form and the offer redemption refuse, the admin door only warns,
and the member's own profile is a ratchet rather than a rule — [R] is the case
that would have broken 1,683 people's bio saves if it were a plain rule. That
ratchet is deliberately NOT tightened along with the rest: the hard rule is on
new names, and existing Latin-named members must still be able to save a bio.

Turnstile is stubbed out, not worked around: it sits in front of the name check
in the real endpoint, so leaving it live would mean every signup here failed
for the wrong reason and the name rule would never be reached.
"""
import os, sys
os.environ.setdefault("SECRET_KEY", "dummy_secret_for_import_check")

# Approve the target database before anything imports the app.
from _acceptance_guard import require_scratch_database  # noqa: E402
require_scratch_database()

from fastapi.testclient import TestClient
import main
from app.database import SessionLocal, engine
from app.models import Base
from app import models as M
from app.routers import users as users_router
from app.routers import atlas as atlas_router
from app.services.name_utils import (ARABIC_NAME_MESSAGE, arabic_name_suggestion,
                                     is_arabic_name)

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if (detail and not cond) else ""))

from sqlalchemy import text as _text
with engine.begin() as _c:
    _c.execute(_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── Stubs. Turnstile guards the endpoint ahead of the name check; email is not
#    what is under test here. ────────────────────────────────────────────────
users_router.verify_turnstile = lambda token, ip=None: True
users_router.send_verification_email_async = lambda *a, **k: None
atlas_router.send_atlas_otp_email = lambda to, code: None

c = TestClient(main.app)

import bcrypt
def pw(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def signup(first, last, email, **extra):
    body = {"first_name": first, "last_name": last, "email": email,
            "password": "Str0ng!passw0rd", "country": "Egypt",
            "governorate": "Cairo", "turnstile_token": "x"}
    body.update(extra)
    r = c.post("/auth/register", json=body)
    if r.status_code == 201:
        CREATED_AS[email] = (first + " " + last).strip()
    return r

CREATED_AS = {}

def mkuser(email, full_name, **kw):
    CREATED_AS[email] = full_name
    kw.setdefault("hashed_password", pw("originalpw"))
    kw.setdefault("is_verified", True)
    kw.setdefault("is_active", True)
    first, _, last = full_name.partition(" ")
    u = M.User(email=email, full_name=full_name, first_name=first, last_name=last, **kw)
    db.add(u); db.commit(); db.refresh(u)
    return u

def token_for(user):
    r = c.post("/auth/login", json={"email": user.email, "password": "originalpw"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}

print("\n── Door 1: the signup form ──────────────────────────────────────")

r = signup("Mohamed محمد", "علي", "half@t.co")
check("[1a] `Mohamed محمد` is rejected — half a name is not an Arabic name",
      r.status_code == 422 and ARABIC_NAME_MESSAGE in r.text, (r.status_code, r.text[:120]))

r = signup("Mohamed", "Ali", "latin@t.co")
check("[1b] a fully Latin name is rejected", r.status_code == 422, (r.status_code, r.text[:120]))

r = signup("محمد", "علي", "arabic@t.co")
check("[1c] an Arabic name is accepted", r.status_code == 201, (r.status_code, r.text[:160]))

r = signup("عبد الرحمن", "علي", "compound@t.co")
u = db.query(M.User).filter_by(email="compound@t.co").first()
check("[1d] a compound Arabic name is accepted and kept whole",
      r.status_code == 201 and u and u.first_name == "عبد الرحمن" and u.full_name == "عبد الرحمن علي",
      (r.status_code, u.first_name if u else None))

r = signup("Mohamed", "Ali", "optout@t.co", latin_name_ok=True)
u = db.query(M.User).filter_by(email="optout@t.co").first()
check("[1e] the old opt-out flag is ignored — no account, same refusal",
      r.status_code == 422 and ARABIC_NAME_MESSAGE in r.text and u is None,
      (r.status_code, r.text[:120]))

r = signup("محمد1", "علي", "digits@t.co")
check("[1f] digits in a name are rejected", r.status_code == 422, (r.status_code,))

# نص الاسم عربي ونصه لاتيني — الشكل اللي المالك قال إنه مايوجدش في أي باب.
# الفحص هنا على كل خانة لوحدها، فالاتنين دول لازم يقعوا حتى وإن كل خانة
# فيهم لوحدها سليمة في لغتها.
r = signup("محمد", "Salah", "arfirst@t.co")
check("[1g] an Arabic first name with a Latin surname is rejected",
      r.status_code == 422 and ARABIC_NAME_MESSAGE in r.text, (r.status_code, r.text[:120]))

r = signup("Mohamed", "صلاح", "arlast@t.co")
check("[1h] a Latin first name with an Arabic surname is rejected",
      r.status_code == 422 and ARABIC_NAME_MESSAGE in r.text, (r.status_code, r.text[:120]))

print("\n── Door 3: atlas offer redemption ───────────────────────────────")

db.add(M.LegacyEmail(email="offer@t.co", full_name="Roster Name")); db.commit()
c.post("/atlas/send-otp", json={"email": "offer@t.co"})
otp = db.query(M.User).filter_by(email="offer@t.co").first()
code = None
for store in (getattr(atlas_router, "_otp_store", None), getattr(atlas_router, "otp_store", None)):
    if isinstance(store, dict) and "offer@t.co" in store:
        v = store["offer@t.co"]
        code = v[0] if isinstance(v, (tuple, list)) else (v.get("code") if isinstance(v, dict) else v)
if code:
    r = c.post("/atlas/verify-otp", json={"email": "offer@t.co", "otp": code,
                                          "full_name": "Mohamed Ali", "password": "Str0ng!pw"})
    check("[3a] offer redemption refuses a Latin name",
          r.status_code == 422 and ARABIC_NAME_MESSAGE in r.text, (r.status_code, r.text[:120]))
    r = c.post("/atlas/verify-otp", json={"email": "offer@t.co", "otp": code,
                                          "full_name": "Mohamed Ali", "password": "Str0ng!pw",
                                          "latin_name_ok": True})
    check("[3b] the old opt-out flag is ignored here too",
          r.status_code == 422 and ARABIC_NAME_MESSAGE in r.text, (r.status_code, r.text[:120]))
    r = c.post("/atlas/verify-otp", json={"email": "offer@t.co", "otp": code,
                                          "full_name": "منى صلاح", "password": "Str0ng!pw"})
    u = db.query(M.User).filter_by(email="offer@t.co").first()
    check("[3c] …and an Arabic name still redeems the offer",
          r.status_code == 200 and u and u.full_name == "منى صلاح",
          (r.status_code, u.full_name if u else None, r.text[:120]))
else:
    check("[3] atlas OTP store not reachable — door not exercised", False, "could not read the OTP")

print("\n── Door 4: an admin creates a member — warn, never block ────────")

owner = mkuser("owner@t.co", "المالك الكبير", is_admin=True, is_owner=True)
h = token_for(owner)
r = c.post("/admin/users/add", headers=h, json={"full_name": "Foreign Member", "email": "foreign@t.co",
                                            "password": "Str0ng!pw", "country": "Ghana"})
check("[4a] the admin door creates the account anyway", r.status_code in (200, 201), (r.status_code, r.text[:160]))
check("[4b] …and says so in the response",
      r.status_code in (200, 201) and r.json().get("name_warning") == ARABIC_NAME_MESSAGE,
      r.json() if r.status_code in (200, 201) else r.text[:120])
r = c.post("/admin/users/add", headers=h, json={"full_name": "أحمد سمير", "email": "arabicadmin@t.co",
                                            "password": "Str0ng!pw", "country": "Egypt"})
check("[4c] no warning when the name is Arabic",
      r.status_code in (200, 201) and r.json().get("name_warning") is None, r.text[:120])

print("\n── Door 5: the member edits their own profile — a ratchet ───────")

latin = mkuser("latinmember@t.co", "Youssef Sabet")
hl = token_for(latin)
r = c.put("/profile/me", headers=hl, json={"full_name": "Youssef Sabet", "bio": "بايو جديد"})
db.refresh(latin)
check("[R] a Latin-named member saves a bio and keeps their name",
      r.status_code == 200 and latin.bio == "بايو جديد" and latin.full_name == "Youssef Sabet",
      (r.status_code, r.text[:160]))

r = c.put("/profile/me", headers=hl, json={"full_name": "Youssef Sabett", "bio": "بايو جديد"})
db.refresh(latin)
check("[5b] a Latin-named member can still fix a typo in their name",
      r.status_code == 200 and latin.full_name == "Youssef Sabett", (r.status_code, latin.full_name))

arab = mkuser("arabmember@t.co", "أحمد سمير")
ha = token_for(arab)
r = c.put("/profile/me", headers=ha, json={"full_name": "Ahmed Samir"})
db.refresh(arab)
check("[5c] an Arabic-named member cannot switch to Latin",
      r.status_code == 422 and arab.full_name == "أحمد سمير", (r.status_code, arab.full_name))

r = c.put("/profile/me", headers=ha, json={"full_name": "أحمد سمير علي"})
db.refresh(arab)
check("[5d] …but can still change their Arabic name",
      r.status_code == 200 and arab.full_name == "أحمد سمير علي", (r.status_code, arab.full_name))

r = c.put("/profile/me", headers=ha, json={"bio": "بايو من غير اسم"})
db.refresh(arab)
check("[5e] a save that carries no name at all is untouched by the rule",
      r.status_code == 200 and arab.bio == "بايو من غير اسم", (r.status_code, r.text[:120]))

print("\n── §2.4 The onboarding step (Google signups) ────────────────────")

# A Google signup: verified, paid, name is whatever Google had.
goog = mkuser("google@t.co", "Mohamed Salah", onboarding_completed=False)
hg = token_for(goog)

st = c.get("/profile/onboarding-status", headers=hg).json()
check("[G1] a Latin-named member is asked", st.get("needs_arabic_name") is True, st)
check("[G2] the field is prefilled with the map's reading — a correction, not a typing task",
      st.get("suggested_name") == "محمد صلاح", st)

# الاقتراح هو قيمة الخانة الافتراضية، يعني ممكن يتبعت زي ما هو. فلازم يعدّي
# نفس القاعدة اللي بترفض — واقتراح نص نص كان بيعلّم الشكل الممنوع نفسه.
mixed = []
for stored in ("Mohamed Salah", "Nabil Ahmed", "Mohamed Elsayed", "Radhouane Bouzid",
               "محمد Salah", "Mohamed محمد", "Abdelrahman Salah", "ALAA S. N. AL-ZAYYAN"):
    sug = arabic_name_suggestion(stored)
    if sug and not is_arabic_name(sug):
        mixed.append((stored, sug))
check("[G2b] no suggestion is ever half-Arabic — it is a full Arabic name or nothing",
      not mixed, mixed)
check("[G2c] both tokens known → the whole name is suggested",
      arabic_name_suggestion("Nabil Ahmed") == "نبيل أحمد", arabic_name_suggestion("Nabil Ahmed"))
check("[G2d] only the first known → the surname is left for the member to type",
      arabic_name_suggestion("Mohamed Elsayed") == "محمد", arabic_name_suggestion("Mohamed Elsayed"))
check("[G2e] neither known → no prefill at all",
      arabic_name_suggestion("Radhouane Bouzid") == "", arabic_name_suggestion("Radhouane Bouzid"))

r = c.post("/profile/complete-onboarding", headers=hg,
           json={"full_name": "Mohamed Salah", "social_media_url": "https://x.com/a"})
db.refresh(goog)
check("[G3] a Latin name is refused at the step",
      r.status_code == 422 and goog.full_name == "Mohamed Salah" and not goog.onboarding_completed,
      (r.status_code, goog.full_name, goog.onboarding_completed))

# نفس الاسم اللي الفورم بيقترحه غلط كان هيبقى مقبول لو الباب ده بيسيب النص
# نص يعدّي. مش بيعدّي — والاتنين دول هما الحالة اللي المالك سمّاها بالظبط.
r = c.post("/profile/complete-onboarding", headers=hg,
           json={"full_name": "محمد Salah", "social_media_url": "https://x.com/a"})
db.refresh(goog)
check("[G3b] `محمد Salah` is refused at the step — half a name is not an Arabic name",
      r.status_code == 422 and goog.full_name == "Mohamed Salah" and not goog.onboarding_completed,
      (r.status_code, goog.full_name))

r = c.post("/profile/complete-onboarding", headers=hg,
           json={"full_name": "Mohamed محمد", "social_media_url": "https://x.com/a"})
db.refresh(goog)
check("[G3c] `Mohamed محمد` is refused too — the order does not save it",
      r.status_code == 422 and goog.full_name == "Mohamed Salah" and not goog.onboarding_completed,
      (r.status_code, goog.full_name))

r = c.post("/profile/complete-onboarding", headers=hg,
           json={"full_name": "محمد صلاح", "social_media_url": "https://x.com/a"})
db.refresh(goog)
check("[G4] the member's own Arabic name is stored, and onboarding completes",
      r.status_code == 200 and goog.full_name == "محمد صلاح"
      and goog.first_name == "محمد" and goog.last_name == "صلاح"
      and goog.onboarding_completed is True,
      (r.status_code, goog.full_name, goog.first_name, goog.last_name))
check("[G4b] every one of the three stored name columns is Arabic",
      all(is_arabic_name(v) for v in (goog.full_name, goog.first_name, goog.last_name)),
      (goog.full_name, goog.first_name, goog.last_name))

# الرد بيرجّع الاسم عشان المتصفح يحدّث نسخته المخزّنة على طول. من غير الحتة
# دي الشهادة اللي تتسحب قبل تسجيل خروج بتطلع بالاسم اللاتيني القديم.
body = r.json()
check("[G4c] the response carries the stored name back for the browser cache",
      body.get("full_name") == "محمد صلاح" and body.get("first_name") == "محمد"
      and body.get("last_name") == "صلاح", body)

st = c.get("/profile/onboarding-status", headers=hg).json()
check("[G5] …and is not asked again", st.get("needs_arabic_name") is False, st)

# There is no way out of the step any more. This member's name genuinely is
# not written in Arabic, which used to be the whole reason the opt-out existed.
optg = mkuser("optgoogle@t.co", "ALAA S. N. AL-ZAYYAN", onboarding_completed=False)
ho = token_for(optg)
r = c.post("/profile/complete-onboarding", headers=ho,
           json={"latin_name_ok": True, "social_media_url": "https://x.com/a"})
db.refresh(optg)
check("[G6] the old opt-out flag does not complete onboarding any more",
      r.status_code == 422 and optg.onboarding_completed is False
      and optg.full_name == "ALAA S. N. AL-ZAYYAN",
      (r.status_code, optg.full_name, optg.onboarding_completed))
st = c.get("/profile/onboarding-status", headers=ho).json()
check("[G7] …and the member is still asked", st.get("needs_arabic_name") is True, st)

# Sending nothing at all is the same back door the PATCH was: the step used to
# complete regardless, which was harmless only while «اسمي مش بالعربي» was a
# legitimate answer. It is not an answer any more.
r = c.post("/profile/complete-onboarding", headers=ho,
           json={"social_media_url": "https://x.com/a"})
db.refresh(optg)
check("[G7b] completing with no name at all is refused",
      r.status_code == 422 and optg.onboarding_completed is False, r.status_code)

r = c.post("/profile/complete-onboarding", headers=ho, json={"full_name": "علاء زيان"})
db.refresh(optg)
check("[G7c] …and writing the name in Arabic finishes it",
      r.status_code == 200 and optg.full_name == "علاء زيان"
      and optg.onboarding_completed is True, (r.status_code, optg.full_name))

# Already Arabic: never asked at all.
ar2 = mkuser("alreadyarabic@t.co", "سمير أحمد", onboarding_completed=False)
st = c.get("/profile/onboarding-status", headers=token_for(ar2)).json()
check("[G8] an Arabic-named member is never asked",
      st.get("needs_arabic_name") is False and st.get("suggested_name") == "", st)

# Onboarding sits behind payment — the owner accepted that a Google signup who
# never pays keeps their Latin name and is never asked.
# The owner was explicit about this one: a Google signup who never paid keeps
# their Latin name and is left alone. The hard rule did not change that — the
# step sits behind payment, so nobody asks, nothing is renamed, and nothing
# blocks them. They are asked the first time they pay and land in onboarding.
unpaid = mkuser("unpaid@t.co", "Karim Latin", is_active=False, onboarding_completed=False)
hu = token_for(unpaid)
r = c.get("/profile/onboarding-status", headers=hu)
check("[G9] an unpaid member never reaches the step (402)", r.status_code == 402, r.status_code)
r2 = c.post("/profile/complete-onboarding", headers=hu, json={"full_name": "كريم عربي"})
db.refresh(unpaid)
check("[G9b] …and nothing renames them while they have not paid",
      r2.status_code == 402 and unpaid.full_name == "Karim Latin",
      (r2.status_code, unpaid.full_name))

# A name with no reading in the map: the field comes up empty, nothing invented.
noread = mkuser("noread@t.co", "Radhouane Bouzid", onboarding_completed=False)
st = c.get("/profile/onboarding-status", headers=token_for(noread)).json()
check("[G10] an unknown name is not guessed at — the field is left empty",
      st.get("needs_arabic_name") is True and st.get("suggested_name") == "", st)

print("\n── Door 6: the flag itself — PATCH /users/me/complete-onboarding ─")

# العلامة دي هي اللي الحارس بيقرأها. باب تاني بيرفعها من غير شرط الاسم معناه
# إن الباب الأول اللي بيرفض مالوش أي لازمة — العضو بينده على ده وخلاص.
flagger = mkuser("flag@t.co", "Karim Latin", onboarding_completed=False)
hf = token_for(flagger)
r = c.patch("/users/me/complete-onboarding", headers=hf)
db.refresh(flagger)
check("[F1] a member who still owes an Arabic name cannot raise the flag directly",
      r.status_code == 422 and flagger.onboarding_completed is False,
      (r.status_code, flagger.onboarding_completed))

r = c.post("/profile/complete-onboarding", headers=hf, json={"full_name": "كريم سمير"})
db.refresh(flagger)
check("[F2] …and once the name is Arabic the same call goes through",
      r.status_code == 200 and c.patch("/users/me/complete-onboarding", headers=hf).status_code == 200,
      (r.status_code, flagger.full_name))

# A row carrying the retired flag. Nothing reads it any more, so it no longer
# buys an exemption — and the member's stored name is still not touched.
opted = mkuser("flagopt@t.co", "Latin Optout", latin_name_ok=True, onboarding_completed=False)
r = c.patch("/users/me/complete-onboarding", headers=token_for(opted))
db.refresh(opted)
check("[F3] a row with the retired opt-out flag is no longer exempt",
      r.status_code == 422 and opted.onboarding_completed is False
      and opted.full_name == "Latin Optout",
      (r.status_code, opted.full_name, opted.onboarding_completed))

arabic_flag = mkuser("flagar@t.co", "هدى سمير", onboarding_completed=False)
r = c.patch("/users/me/complete-onboarding", headers=token_for(arabic_flag))
db.refresh(arabic_flag)
check("[F4] an Arabic-named member is unaffected",
      r.status_code == 200 and arabic_flag.onboarding_completed is True, r.status_code)

print("\n── No stored name is ever rewritten ─────────────────────────────")

# Every name written by a fixture, against every name in the table now. The
# only rows allowed to differ are the ones a member changed on purpose above.
MEMBER_CHANGED = {"google@t.co", "arabmember@t.co", "latinmember@t.co", "flag@t.co",
                  "optgoogle@t.co", "offer@t.co"}
drift = {}
for u in db.query(M.User).all():
    if u.email in MEMBER_CHANGED:
        continue
    want = CREATED_AS.get(u.email)
    if want is not None and u.full_name != want:
        drift[u.email] = (want, u.full_name)
check("[N] no name changed except the ones a member typed", not drift, drift)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:"); [print("   -", f) for f in FAIL]
sys.exit(1 if FAIL else 0)
