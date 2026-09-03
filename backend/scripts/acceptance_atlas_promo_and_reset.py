"""Acceptance checks for the Atlas free-month promo and the password reset flow.

Runs against a throwaway DB, same shape as acceptance_security.py:

    DATABASE_URL=postgresql://...:5432/ghawy_test python backend/scripts/acceptance_atlas_promo_and_reset.py

The three requirements named in the brief for "one free month per round" are
checked explicitly and marked [C1]/[C2]/[C3]:

  C1  a member who redeemed round 1 can redeem again now, and the 30 days are
      ADDED to whatever they had left rather than replacing it
  C2  the same member cannot redeem twice inside round 2
  C3  is_legacy_redeemed is never cleared — it is the historical record

No mail is sent: both OTP senders are replaced with recorders, and the codes are
read back out of the store / the column rather than out of an inbox.
"""
import os, sys, datetime
os.environ.setdefault("SECRET_KEY", "dummy_secret_for_import_check")

# Approve the target database before anything imports the app: `import main`
# writes to the database on import, so the guard has to come first.
from _acceptance_guard import require_scratch_database  # noqa: E402
require_scratch_database()

from fastapi.testclient import TestClient
import main
from app.database import SessionLocal, engine
from app.models import Base
from app import models as M
from app.routers import atlas as atlas_router
from app.routers import users as users_router

PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ok   " if cond else "  FAIL ") + name + (("  -> " + str(detail)) if (detail and not cond) else ""))

from sqlalchemy import text as _text
with engine.begin() as _c:
    _c.execute(_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── No SMTP. Recorders instead, so a broken send cannot masquerade as a pass. ──
sent_atlas, sent_reset = [], []
atlas_router.send_atlas_otp_email = lambda to, code: sent_atlas.append((to, code))
users_router.send_password_reset_email = lambda to, code: sent_reset.append((to, code))

c = TestClient(main.app)
NOW = datetime.datetime.utcnow()

import bcrypt
def pw(p): return bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode()

def mkuser(email, **kw):
    kw.setdefault("full_name", "Roster Member")
    kw.setdefault("hashed_password", pw("originalpw"))
    kw.setdefault("is_verified", True)
    u = M.User(email=email, **kw)
    db.add(u); db.commit(); db.refresh(u)
    return u

def roster(email, name=None):
    db.add(M.LegacyEmail(email=email, full_name=name)); db.commit()

# ── Fixtures ─────────────────────────────────────────────────────────────────
for e in ["round1@t.co", "noaccount@t.co", "paid@t.co", "google@t.co",
          "unverified@t.co", "MixedCase@t.co".lower(), "attempts@t.co", "cooldown@t.co"]:
    roster(e, "Roster Name")

# redeemed round 1, mid-subscription with 10 days left
u_round1 = mkuser("round1@t.co", is_legacy_redeemed=True, legacy_promo_round=1,
                  end_at=NOW + datetime.timedelta(days=10), is_active=True,
                  onboarding_completed=True, full_name="Original Name")
# paid member — the source that is true of them must survive redeeming
u_paid = mkuser("paid@t.co", subscription_source="kashier", onboarding_completed=True)
# Google account — the sentinel password must survive
u_google = mkuser("google@t.co", hashed_password="google_oauth_abc", onboarding_completed=True)
# signed up but never verified — nothing to sign into yet
u_unver = mkuser("unverified@t.co", is_verified=False, onboarding_completed=False)
# stored with different case than the roster row
u_mixed = mkuser("MixedCase@t.co", onboarding_completed=True)   # roster row is lowercase, above
u_attempts = mkuser("attempts@t.co", onboarding_completed=True)
u_cool = mkuser("cooldown@t.co", onboarding_completed=True)

def code_for(email):
    return atlas_router._otp_store[email]["code"]

def send(email):
    return c.post("/atlas/send-otp", json={"email": email})

def verify(email, code=None, **extra):
    body = {"email": email, "otp": code if code is not None else code_for(email)}
    body.update(extra)
    return c.post("/atlas/verify-otp", json=body)

print("\n── Atlas roster gate ──")
r = send("stranger@nowhere.com")
check("an address that is not on the roster is refused (404)", r.status_code == 404, r.status_code)
check("the refusal names Whop so the member knows which address to use",
      "Whop" in r.json().get("detail", ""), r.json())

print("\n── needs_credentials ──")
r = send("noaccount@t.co")
check("no account at all -> needs_credentials true",
      r.status_code == 200 and r.json()["needs_credentials"] is True, r.json())
r = send("unverified@t.co")
check("account exists but was never verified -> needs_credentials true",
      r.json()["needs_credentials"] is True, r.json())
r = send("paid@t.co")
check("a usable account -> needs_credentials false",
      r.json()["needs_credentials"] is False, r.json())
r = send("google@t.co")
check("a Google account counts as usable -> needs_credentials false",
      r.json()["needs_credentials"] is False, r.json())
check("the OTP mail was handed to the sender, not skipped", len(sent_atlas) >= 4, len(sent_atlas))

print("\n── C: one free month per round ──")
before_end = u_round1.end_at
r = send("round1@t.co")
check("[C1] a round-1 redeemer is offered the month again (not 409)", r.status_code == 200, r.text)
r = verify("round1@t.co")
check("[C1] the round-1 redeemer can redeem round 2", r.status_code == 200, r.text)
db.refresh(u_round1)
gained = (u_round1.end_at - before_end).days
check(f"[C1] 30 days ADDED to the 10 they had left, not overwritten (gained {gained})",
      gained == 30, f"{before_end} -> {u_round1.end_at}")
check("[C1] round is stamped to 2", u_round1.legacy_promo_round == 2, u_round1.legacy_promo_round)
check("[C3] is_legacy_redeemed is still true, never cleared", u_round1.is_legacy_redeemed is True)

r = send("round1@t.co")
check("[C2] the same member cannot start round 2 twice (409)", r.status_code == 409, r.status_code)
r = verify("round1@t.co", code="000000")
check("[C2] and verify-otp refuses it too, not just send-otp", r.status_code == 409, r.status_code)
db.refresh(u_round1)
check("[C3] is_legacy_redeemed survives the refusal", u_round1.is_legacy_redeemed is True)

print("\n── an existing account is not overwritten ──")
old_hash, old_name = u_paid.hashed_password, u_paid.full_name
send("paid@t.co")
r = verify("paid@t.co", full_name="Attacker Name", password="attackerpw")
check("redeeming succeeds for an account that already exists", r.status_code == 200, r.text)
db.refresh(u_paid)
check("the password is untouched even though one was sent", u_paid.hashed_password == old_hash)
check("the name is untouched even though one was sent", u_paid.full_name == old_name, u_paid.full_name)
check("onboarding_completed is not reset", u_paid.onboarding_completed is True)
check("a member who paid keeps subscription_source='kashier'",
      u_paid.subscription_source == "kashier", u_paid.subscription_source)
check("they are sent to the dashboard, not back through onboarding",
      r.json()["redirect"] == "/dashboard.html", r.json()["redirect"])

send("google@t.co")
r = verify("google@t.co", full_name="Attacker", password="attackerpw")
db.refresh(u_google)
check("a Google account's google_oauth_ sentinel survives redemption",
      u_google.hashed_password == "google_oauth_abc", u_google.hashed_password)
check("an empty subscription_source is filled with legacy_promo",
      u_google.subscription_source == "legacy_promo", u_google.subscription_source)

print("\n── an account being created ──")
send("noaccount@t.co")
r = verify("noaccount@t.co", full_name="New Member", password="short")
check("a password under 6 characters is refused (422)", r.status_code == 422, r.status_code)
r = verify("noaccount@t.co", full_name="A", password="goodpassword")
check("a one-character name is refused (422)", r.status_code == 422, r.status_code)
r = verify("noaccount@t.co", full_name="New Member", password="goodpassword")
check("the account is created", r.status_code == 200, r.text)
check("a new member is sent through onboarding",
      r.json()["redirect"] == "/onboarding.html", r.json().get("redirect"))
u_new = db.query(M.User).filter(M.User.email == "noaccount@t.co").first()
check("the new account is verified and active", u_new.is_verified and u_new.is_active)
check("the new account has 30 days", 29 <= (u_new.end_at - NOW).days <= 30, u_new.end_at)
check("onboarding_completed is False on a brand-new account", u_new.onboarding_completed is False)
check("the file cookie is minted the way /auth/login does it",
      "ghawy_files" in r.cookies or "ghawy_files" in str(r.headers.get("set-cookie", "")),
      r.headers.get("set-cookie"))
me = c.get("/profile/me", headers={"Authorization": "Bearer " + r.json()["access_token"]})
check("the issued token is a working session token", me.status_code == 200, me.status_code)

print("\n── case-insensitive matching ──")
send("mixedcase@t.co")
r = verify("mixedcase@t.co", full_name="Should Be Ignored", password="ignoredpw")
db.refresh(u_mixed)
check("a roster address matches an account stored with different case",
      r.status_code == 200 and u_mixed.legacy_promo_round == 2, (r.status_code, u_mixed.legacy_promo_round))
check("...and it grants the month on that account instead of making a second one",
      db.query(M.User).filter(M.User.email.ilike("mixedcase@t.co")).count() == 1)

print("\n── OTP hardening ──")
send("cooldown@t.co")
r = send("cooldown@t.co")
check("a second code inside 60s is refused server-side (429)", r.status_code == 429, r.status_code)

send("attempts@t.co")
codes = [c.post("/atlas/verify-otp", json={"email": "attempts@t.co", "otp": "000000"}).status_code
         for _ in range(5)]
check("five wrong guesses all fail", all(s == 400 for s in codes), codes)
check("the code is burned after the fifth", "attempts@t.co" not in atlas_router._otp_store)
r = verify("attempts@t.co", code="000000")
check("and the burned code cannot be used even if guessed right afterwards",
      r.status_code == 400, r.status_code)
check("no OTP was ever logged (the store is the only place it lives)",
      all(len(code) == 6 and code.isdigit() for _, code in sent_atlas))

print("\n── ATLAS_PROMO_ROUND is the whole switch ──")
check("bumping the constant is what reopens the promo",
      atlas_router.ATLAS_PROMO_ROUND == 2, atlas_router.ATLAS_PROMO_ROUND)
atlas_router.ATLAS_PROMO_ROUND = 3
r = send("round1@t.co")
check("a round-3 promo is offered to a member who has spent rounds 1 and 2",
      r.status_code == 200, r.status_code)
atlas_router.ATLAS_PROMO_ROUND = 2

# ══════════════════════════════════════════════════════════════════════════
#  Password reset
# ══════════════════════════════════════════════════════════════════════════
print("\n── password reset ──")
u_reset = mkuser("reset@t.co", onboarding_completed=True, is_active=True)
login = c.post("/auth/login", json={"email": "reset@t.co", "password": "originalpw"})
check("the member can log in with the original password", login.status_code == 200, login.text)
old_token = login.json()["access_token"]

r = c.post("/auth/forgot-password", json={"email": "nobody@nowhere.com"})
unknown_msg = r.json().get("message")
check("an unknown address gets a 200, not a 404", r.status_code == 200, r.status_code)
r = c.post("/auth/forgot-password", json={"email": "reset@t.co"})
check("a known address gets the SAME message — no account enumeration",
      r.status_code == 200 and r.json().get("message") == unknown_msg, r.json())
r2 = c.post("/auth/forgot-password", json={"email": "reset@t.co"})
check("the resend cooldown answers with that same message too, not a 429",
      r2.status_code == 200 and r2.json().get("message") == unknown_msg, r2.status_code)

r = c.post("/auth/forgot-password", json={"email": "google@t.co"})
check("a Google account is told to use Google instead of waiting for a code",
      r.status_code == 400 and "Google" in r.json().get("detail", ""), r.json())

db.refresh(u_reset)
reset_code = u_reset.password_reset_code
check("the reset code is stored in its own column, not verification_code",
      reset_code is not None and u_reset.verification_code is None, reset_code)
check("the reset mail was handed to the sender", any(e == "reset@t.co" for e, _ in sent_reset))

r = c.post("/auth/verify-reset-code", json={"email": "reset@t.co", "code": "000000"})
check("a wrong code is refused", r.status_code == 400, r.status_code)
r = c.post("/auth/verify-reset-code", json={"email": "reset@t.co", "code": reset_code})
check("the right code is traded for a reset token", r.status_code == 200 and r.json().get("reset_token"), r.text)
reset_token = r.json()["reset_token"]

db.refresh(u_reset)
check("the code is NOT cleared at step 2 — step 3 re-checks it",
      u_reset.password_reset_code == reset_code)

r = c.post("/auth/reset-password", json={"reset_token": reset_token, "password": "short"})
check("a password under 6 characters is refused (422)", r.status_code == 422, r.status_code)
r = c.post("/auth/reset-password", json={"reset_token": reset_token, "password": "brandnewpw"})
check("the password is changed", r.status_code == 200, r.text)

db.refresh(u_reset)
check("the reset code is cleared afterwards", u_reset.password_reset_code is None)
check("is_verified is set — a code that reached that inbox was read out of it",
      u_reset.is_verified is True)

r = c.post("/auth/login", json={"email": "reset@t.co", "password": "brandnewpw"})
check("the member can log in with the new password", r.status_code == 200, r.text)
r = c.post("/auth/login", json={"email": "reset@t.co", "password": "originalpw"})
check("the old password no longer works", r.status_code == 401, r.status_code)

r = c.get("/profile/me", headers={"Authorization": "Bearer " + old_token})
check("token_version was bumped: the session opened before the reset is dead",
      r.status_code == 401, r.status_code)

fresh = c.post("/auth/login", json={"email": "reset@t.co", "password": "brandnewpw"})
r = c.get("/profile/me", headers={"Authorization": "Bearer " + fresh.json()["access_token"]})
check("...while a token issued after the reset still works (so the 401 above is revocation, not a broken probe)",
      r.status_code == 200, r.status_code)

r = c.post("/auth/reset-password", json={"reset_token": reset_token, "password": "thirdpassword"})
check("the reset token cannot be replayed — one token, one password change",
      r.status_code == 400, r.status_code)

print("\n── reset code burns after 5 tries ──")
u_burn = mkuser("burn@t.co", onboarding_completed=True)
c.post("/auth/forgot-password", json={"email": "burn@t.co"})
db.refresh(u_burn)
burn_code = u_burn.password_reset_code
tries = [c.post("/auth/verify-reset-code", json={"email": "burn@t.co", "code": "000000"}).status_code
         for _ in range(5)]
check("five wrong reset codes all fail", all(s == 400 for s in tries), tries)
db.refresh(u_burn)
check("the reset code is burned after the fifth", u_burn.password_reset_code is None)
r = c.post("/auth/verify-reset-code", json={"email": "burn@t.co", "code": burn_code})
check("and the burned code is refused even when it was the right one", r.status_code == 400, r.status_code)

print("\n── nothing sensitive reaches the logs ──")
# Same guard acceptance_security applies to users.py, extended to the two
# routers this branch adds code to. A code in a log file is a code anyone with
# log access can spend.
import inspect, re as _re
for _mod in (atlas_router, users_router):
    _src = inspect.getsource(_mod)
    _leaky = [c for c in _re.findall(r"logger\.(?:info|debug|warning|error)\([^)]*\)", _src)
              if _re.search(r"verification_code|submitted_code|otp|password", c, _re.I)]
    check(f"no log line in {_mod.__name__} carries a code or a password", not _leaky, _leaky)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:")
    for f in FAIL:
        print("  -", f)
sys.exit(1 if FAIL else 0)
