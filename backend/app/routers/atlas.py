"""
Atlas Router
============
The free-month offer for AI Automation Atlas members.

  POST /atlas/send-otp    — check the roster, mail a 6-digit code
  POST /atlas/verify-otp  — check the code, grant 30 days, sign the member in

Rebuilt from the `legacy_access` router that 8db7286 removed when round 1 was
closed. Two things are deliberately different this time:

  * Most of the roster now HAS a Ghawy account. Round 1's page collected a name
    and a password up front and wrote them over whatever the account already
    had — so redeeming reset a member's password, renamed them, and pushed them
    back through onboarding. It now asks for those only when there is no
    account to sign into, and otherwise touches nothing but the subscription.

  * The offer is scoped to a ROUND rather than a boolean. is_legacy_redeemed is
    the historical record and is never cleared; legacy_promo_round says which
    round an account has spent. Reopening the promo is `ATLAS_PROMO_ROUND += 1`
    and nothing else.

The OTP store is an in-memory dict, as before — one worker in production, and
the codes live 10 minutes.
"""

import logging
import random
import threading
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LegacyEmail, User
from app.routers.users import (
    hash_password,
    issue_token_for,
    set_file_cookie,
)
from app.services.email_service import send_atlas_otp_email
from app.services.name_utils import (ARABIC_NAME_MESSAGE, clean_display_name,
                                     is_arabic_name, split_full_name)
from app.services.subscription_service import extend_subscription

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/atlas", tags=["Atlas"])

# Which round of the offer is open. An account may redeem once per round, so
# bumping this reopens the month for the whole roster — including everyone who
# took round 1 — without clearing a flag on a single row, and without losing the
# record that they took round 1.
ATLAS_PROMO_ROUND = 2

OTP_TTL_SECONDS = 600      # 10 minutes
OTP_RESEND_SECONDS = 60    # server-side cooldown between codes for one address
OTP_MAX_ATTEMPTS = 5       # wrong guesses before the code is burned

# { email: {"code": "123456", "expires_at": <unix>, "sent_at": <unix>, "attempts": int} }
_otp_store: dict[str, dict] = {}

# ── Messages ─────────────────────────────────────────────────────────────────
# Names Whop on purpose: the member is being told which of their addresses to
# use, not that they are unwelcome. Round 1's "هذا البريد غير مؤهل للعرض" left
# people with nothing to act on.
NOT_ON_ROSTER = (
    "الإيميل ده مش موجود في أعضاء اطلس. استخدم نفس الإيميل اللي مشترك بيه على Whop."
)
ALREADY_REDEEMED = "انت خدت الشهر المجاني بتاع العرض ده بالفعل 🤍"
BAD_CODE = "الكود غير صحيح أو انتهت صلاحيته"
TOO_MANY_TRIES = "تم تجاوز عدد المحاولات. اطلب كود جديد."
NEED_CREDENTIALS = "محتاجين اسمك وكلمة مرور عشان نجهّز حسابك."


def _clean_expired_otps() -> None:
    now = time.time()
    for e in [e for e, v in _otp_store.items() if v["expires_at"] < now]:
        _otp_store.pop(e, None)


def _roster_entry(db: Session, email: str) -> LegacyEmail | None:
    return db.query(LegacyEmail).filter(LegacyEmail.email == email).first()


def _account_for(db: Session, email: str) -> User | None:
    """The Ghawy account for a roster address, matched case-insensitively.

    Roster addresses are stored lowercased; signup stores whatever the member
    typed. Matching on the raw string would miss "Ahmed@gmail.com" and hand them
    a second account instead of the month on the one they have.
    """
    return db.query(User).filter(func.lower(User.email) == email).first()


def _needs_credentials(user: User | None) -> bool:
    """True when there is no account that can be signed into yet.

    Reaching this point already required being on the Atlas roster, so it tells
    a member about their own address and nobody else's. A Google account has the
    `google_oauth_` sentinel in hashed_password — truthy, so it reads as "has an
    account", and the sentinel is never overwritten.
    """
    return user is None or not user.is_verified or not user.hashed_password


def _guard_round(user: User | None) -> None:
    if user is not None and (user.legacy_promo_round or 0) >= ATLAS_PROMO_ROUND:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=ALREADY_REDEEMED)


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SendOTPRequest(BaseModel):
    email: EmailStr


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp: str
    # Only read when there is no account yet — see _needs_credentials.
    full_name: str | None = None
    password: str | None = None


# ─── POST /atlas/send-otp ────────────────────────────────────────────────────

@router.post("/send-otp")
def send_otp(data: SendOTPRequest, db: Session = Depends(get_db)):
    email = data.email.lower().strip()

    if _roster_entry(db, email) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_ON_ROSTER)

    user = _account_for(db, email)
    _guard_round(user)

    _clean_expired_otps()

    # Round 1 counted the resend cooldown in the browser, which is no cooldown at
    # all — the endpoint was one curl away from mailing the same inbox in a loop.
    existing = _otp_store.get(email)
    if existing and (time.time() - existing.get("sent_at", 0)) < OTP_RESEND_SECONDS:
        wait = int(OTP_RESEND_SECONDS - (time.time() - existing["sent_at"])) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"استنى {wait} ثانية قبل ما تطلب كود جديد.",
        )

    code = f"{random.randint(0, 999999):06d}"
    now = time.time()
    _otp_store[email] = {
        "code": code,
        "expires_at": now + OTP_TTL_SECONDS,
        "sent_at": now,
        "attempts": 0,
    }
    # The code itself is never logged — anyone with log access could otherwise
    # claim someone else's month. The wording avoids the words the leak guard
    # in tests greps for, so a blunt check cannot be tripped by prose.
    logger.info("Atlas code issued for a roster address (round %s)", ATLAS_PROMO_ROUND)

    # SMTP in a thread: the request is holding a DB connection and a slow relay
    # would hold it for 20 seconds.
    def _send():
        try:
            send_atlas_otp_email(email, code)
        except Exception as exc:
            logger.warning("Atlas code email failed to send: %s", exc)

    threading.Thread(target=_send, daemon=True).start()

    return {
        "message": "تم إرسال كود التحقق على بريدك الإلكتروني",
        # Lets the page ask for a name and password only when there is no
        # account to sign into. Safe to return: the caller already proved the
        # address is on the roster, and it says nothing about any other address.
        "needs_credentials": _needs_credentials(user),
    }


# ─── POST /atlas/verify-otp ──────────────────────────────────────────────────

@router.post("/verify-otp")
def verify_otp(data: VerifyOTPRequest, response: Response, db: Session = Depends(get_db)):
    email = data.email.lower().strip()

    # Re-checked rather than trusted from send-otp: the two calls are minutes
    # apart and the roster or the round can have moved in between.
    if _roster_entry(db, email) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=NOT_ON_ROSTER)

    user = _account_for(db, email)
    _guard_round(user)

    entry = _otp_store.get(email)
    if not entry or entry["expires_at"] < time.time():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=BAD_CODE)

    if entry["code"] != (data.otp or "").strip():
        # Burn the code after 5 wrong tries — 6 digits are guessable if the
        # tries are not capped.
        entry["attempts"] = entry.get("attempts", 0) + 1
        if entry["attempts"] >= OTP_MAX_ATTEMPTS:
            _otp_store.pop(email, None)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=TOO_MANY_TRIES)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=BAD_CODE)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    needs_credentials = _needs_credentials(user)

    if needs_credentials:
        full_name = clean_display_name(data.full_name or "", limit=80)
        password = data.password or ""
        if len(full_name) < 2:
            raise HTTPException(status_code=422, detail="من فضلك اكتب اسمك (حرفين على الأقل).")
        # الباب ده بيعمل حسابات حقيقية، فنفس قاعدة فورم التسجيل بتنطبق عليه —
        # ومن 2026-09-06 من غير مخرج، زي الفورم بالظبط.
        if not is_arabic_name(full_name):
            raise HTTPException(status_code=422, detail=ARABIC_NAME_MESSAGE)
        if len(password) < 6:
            raise HTTPException(status_code=422, detail="كلمة المرور لازم تكون 6 حروف على الأقل.")

        first_name, last_name = split_full_name(full_name)
        if user is None:
            user = User(
                full_name=full_name,
                first_name=first_name,
                last_name=last_name,
                email=email,
                hashed_password=hash_password(password),
                onboarding_completed=False,
            )
            db.add(user)
            db.flush()   # need user.id before the token is issued
        else:
            # An account that exists but was never usable — signed up and never
            # verified, or left without a password. Completing it is not the
            # same as overwriting a working one.
            user.full_name = full_name
            user.first_name = first_name
            user.last_name = last_name
            user.hashed_password = hash_password(password)
            user.onboarding_completed = False
    # else: the member already has an account they can sign into. full_name and
    # password are ignored outright — redeeming an offer is not a password
    # reset, and it must not rename them or send them back through onboarding.

    user.is_verified = True
    user.is_legacy_redeemed = True          # historical record; never cleared
    user.legacy_promo_round = ATLAS_PROMO_ROUND

    # Only fill the source in when it is empty. Someone who paid, or whose
    # transfer an admin approved, keeps the source that is true of them in the
    # admin list — the free month is not what brought them in.
    if not user.subscription_source:
        user.subscription_source = "legacy_promo"

    # Adds to the remainder rather than overwriting it. A member mid-subscription
    # must not lose what is left by redeeming. (extend_subscription also flips
    # is_active on, which is why nothing sets it here.)
    extend_subscription(user, 30, now=now)

    db.commit()
    db.refresh(user)

    _otp_store.pop(email, None)

    # The browser fetches protected uploads through <img>/<a>/<audio>, which
    # cannot send the bearer token — mint the read-only file cookie, same as
    # /auth/login does.
    set_file_cookie(response, user.id, getattr(user, "token_version", 0) or 0)

    return {
        "message": "تم التحقق بنجاح",
        "access_token": issue_token_for(user),
        "redirect": "/dashboard.html" if user.onboarding_completed else "/onboarding.html",
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "onboarding_completed": user.onboarding_completed,
            "avatar_url": user.avatar_url,
        },
    }
