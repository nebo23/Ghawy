# users.py
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from jose import jwt
import bcrypt
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.models import User
from sqlalchemy import func
from app.schemas import (UserRegister, UserLogin, UserOut, Token, VerifyEmailRequest,
                         ResendVerificationRequest, ForgotPasswordRequest,
                         VerifyResetCodeRequest, ResetPasswordRequest)
from app.database import get_db
import os
import random
import logging
import threading
from pathlib import Path
from dotenv import load_dotenv
from app.services.email_service import send_verification_email, send_password_reset_email
from app.services.disposable_emails import is_disposable_email, is_fake_email_pattern
from app.services.name_utils import (ARABIC_NAME_MESSAGE, clean_display_name,
                                     compose_full_name, is_arabic_name)
from app.services.turnstile import verify_turnstile
from app.services.permissions import require_permission, has_permission
from jose import JWTError
from typing import Optional

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days
VERIFICATION_EXPIRE_MINUTES = 15
PASSWORD_RESET_EXPIRE_MINUTES = 15
RESET_TOKEN_EXPIRE_MINUTES = 15

def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    pwd_bytes = plain.encode('utf-8')
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    try:
        return bcrypt.checkpw(pwd_bytes, hashed.encode('utf-8'))
    except ValueError:
        return False

def create_token(user_id: int, token_version: int = 0) -> str:
    """Issue a session token, stamped with the user's current token_version.

    The stamp is what makes a 30-day JWT revocable: get_current_user compares it
    against the column, so bumping the column ends every session that user has.
    """
    expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "ver": token_version, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def issue_token_for(user: User) -> str:
    """create_token for a loaded user — the shape every login path wants."""
    return create_token(user.id, getattr(user, "token_version", 0) or 0)


# ─── File-access cookie ───────────────────────────────────────
# Protected uploads (lesson PDFs, receipts, chat attachments…) are fetched by
# the browser itself through <img>, <a href> and <audio src> — none of which can
# carry an Authorization header. So the file endpoint accepts a cookie instead.
#
# It is deliberately NOT the session JWT. This token carries typ="file" and
# get_current_user refuses it, so a cookie that rides along on every request to
# the origin can only ever read a file the member could already open — never
# call an API, never change anything. SameSite=Lax keeps it off cross-site
# subresource loads, so it cannot be used to hotlink content either.
FILE_TOKEN_COOKIE = "ghawy_files"
FILE_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days; re-minted on every login

def create_file_token(user_id: int, token_version: int = 0) -> str:
    # Carries "ver" for the same reason the session token does: /logout-all and
    # a password reset bump token_version to kill every credential the account
    # has issued, and a 7-day file cookie that ignored it was a copied cookie
    # that still read receipts, course PDFs and DM attachments for a week after
    # the member had locked their account. Tokens minted before this claim
    # existed read as 0, which matches the default, so old cookies keep working
    # until that account's version is actually bumped.
    expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=FILE_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user_id), "typ": "file", "ver": int(token_version or 0), "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )

def set_file_cookie(response, user_id: int, token_version: int = 0) -> None:
    """Attach the file-access cookie to a response (login, OAuth, /files/session)."""
    response.set_cookie(
        key=FILE_TOKEN_COOKIE,
        value=create_file_token(user_id, token_version),
        max_age=FILE_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

# ─── OAuth hand-off cookie ────────────────────────────────────
# Google sign-in used to finish by redirecting to
# /dashboard.html?token=<30-day JWT>. Those pages load GTM, GA4, the Meta Pixel
# and Microsoft Clarity in <head>, and every one of them reads location.href on
# load — so a member's session token was being shipped to three third parties,
# written into nginx's access log ($request), and left in browser history and
# Referer headers. Stripping it after load, as utils.js did, is far too late:
# the analytics snippets have already run.
#
# Nothing sensitive travels in the URL now. The callback puts the session in a
# short-lived HttpOnly cookie and sends the browser to /auth-complete, which
# swaps it for the real token over a same-origin POST. typ="oauth" keeps it from
# being usable as a session credential on its own, and 120 seconds is the whole
# window between the redirect and the page that spends it.
OAUTH_HANDOFF_COOKIE = "ghawy_oauth"
OAUTH_HANDOFF_EXPIRE_SECONDS = 120

def create_handoff_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=OAUTH_HANDOFF_EXPIRE_SECONDS)
    return jwt.encode(
        {"sub": str(user_id), "typ": "oauth", "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )

def set_handoff_cookie(response, user_id: int) -> None:
    response.set_cookie(
        key=OAUTH_HANDOFF_COOKIE,
        value=create_handoff_token(user_id),
        max_age=OAUTH_HANDOFF_EXPIRE_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

def read_handoff_token(token: Optional[str]) -> Optional[int]:
    """The user id inside a hand-off cookie, or None if it is not a valid one."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("typ") != "oauth":
            return None
        return int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None

def generate_verification_code() -> str:
    return f"{random.randint(0, 999999):06d}"

def send_verification_email_bg(email: str, code: str) -> None:
    """SMTP بطيء أحياناً — بنبعت في thread منفصل عشان الـ request يرجع فوراً
    ويسيب الـ DB connection بدل ما يمسكها 20 ثانية والموقع واقع مستنيها."""
    def _run():
        try:
            send_verification_email(email, code)
        except Exception as exc:
            logger.warning("SMTP send failed for %s: %s", email, exc)
    threading.Thread(target=_run, daemon=True).start()

# عدّاد محاولات التحقق الغلط لكل إيميل — الكود بيتحرق بعد 5 محاولات (ضد التخمين).
# in-memory يكفي: worker واحد في production، والكود نفسه صلاحيته 15 دقيقة.
_verify_attempts: dict[str, int] = {}

# Shown to anyone signing up with a throwaway mailbox or an obviously fake
# local part (test@, 123@, aaaa@ …) — 5-10 of those land every day.
FAKE_EMAIL_MESSAGE = "من فضلك سجّل بإيميل حقيقي — الإيميلات المؤقتة أو التجريبية مش مقبولة."

# ─── Register ────────────────────────────────────────────────
@router.post("/register", response_model=UserOut, status_code=201)
def register(data: UserRegister, request: Request, db: Session = Depends(get_db)):
    # "I'm not a robot" check (Cloudflare Turnstile). No-op until the secret key
    # is configured; once it is, a missing/invalid token is rejected here.
    client_ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                 or (request.client.host if request.client else None))
    if not verify_turnstile(data.turnstile_token, client_ip):
        raise HTTPException(
            status_code=403,
            detail="Please complete the 'I'm not a robot' verification and try again.",
        )

    # Block throwaway / temporary mailboxes: real members use real inboxes, and
    # disposable providers are what the account-flood swarm registers through.
    if is_disposable_email(data.email) or is_fake_email_pattern(data.email):
        raise HTTPException(status_code=422, detail=FAKE_EMAIL_MESSAGE)

    # Checked against the cleaned value, not the raw one — otherwise a name made
    # entirely of markup passes the length rule and is then stored as empty.
    first_clean = clean_display_name(data.first_name, limit=40)
    last_clean = clean_display_name(data.last_name, limit=40)
    if len(first_clean) < 2 or len(last_clean) < 2:
        raise HTTPException(
            status_code=422,
            detail="من فضلك اكتب اسمك الأول والأخير (حرفين على الأقل لكل واحد).",
        )

    # الاسم بالعربي مطلوب من الأعضاء الجدد — بس مش قفل. اللي اسمه مش متكتب
    # بالعربي بيعلّم «اسمي مش بالعربي» والفورم بيبعت `latin_name_ok`، فاسمه
    # بيتخزّن زي ما كتبه ومحدش بيسأله تاني. القاعدة على الأسماء الجديدة بس:
    # ولا اسم متخزّن دلوقتي على الروستر بيتلمس ولا بيتراجع.
    #
    # بيتفحص على القيمة المنضّفة — نفس القيمة اللي هتتخزّن، مش اللي اتبعتت.
    if not data.latin_name_ok and not (
            is_arabic_name(first_clean) and is_arabic_name(last_clean)):
        raise HTTPException(status_code=422, detail=ARABIC_NAME_MESSAGE)

    existing_user = db.query(User).filter(User.email == data.email).first()

    verification_code = generate_verification_code()
    verification_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=VERIFICATION_EXPIRE_MINUTES)

    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="This Email Is Already Exists")

        existing_user.first_name = first_clean
        existing_user.last_name = last_clean
        existing_user.full_name = compose_full_name(data.first_name, data.last_name)
        existing_user.latin_name_ok = bool(data.latin_name_ok)
        existing_user.hashed_password = hash_password(data.password)
        existing_user.phone = None
        existing_user.country = data.country
        existing_user.governorate = data.governorate
        existing_user.verification_code = verification_code
        existing_user.verification_expiry = verification_expiry
        user = existing_user
    else:
        user = User(
            full_name=compose_full_name(data.first_name, data.last_name),
            first_name=first_clean,
            last_name=last_clean,
            latin_name_ok=bool(data.latin_name_ok),
            email=data.email,
            hashed_password=hash_password(data.password),
            phone=None,
            country=data.country,
            governorate=data.governorate,
            is_active=False,
            is_verified=False,
            verification_code=verification_code,
            verification_expiry=verification_expiry,
        )
        db.add(user)

    db.commit()
    db.refresh(user)

    # The code itself is never logged: anyone with log access could otherwise
    # complete someone else's signup. Log that one was issued, not what it was.
    logger.info("Verification code issued for user_id=%s", user.id)

    send_verification_email_bg(user.email, verification_code)

    return user

# ─── Login ───────────────────────────────────────────────────
@router.post("/login", response_model=Token)
def login(data: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    # ✅ Google users لازم يسجلوا بـ Google مش بـ password
    if user and user.hashed_password and user.hashed_password.startswith("google_oauth_"):
        raise HTTPException(
            status_code=400,
            detail="الحساب ده مسجل بـ Google، استخدم زر Sign in with Google"
        )

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email Or Password Is Wrong")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please Verify Your Email First")
    # The browser fetches protected uploads through <img>/<a>/<audio>, which
    # cannot send the bearer token — mint the read-only file cookie here.
    set_file_cookie(response, user.id, getattr(user, "token_version", 0) or 0)
    return {
        "access_token": issue_token_for(user),
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "onboarding_completed": user.onboarding_completed,
            "avatar_url": user.avatar_url
        }
    }

# ─── Token (Swagger) ─────────────────────────────────────────
@router.post("/token", response_model=Token)
def token_login(response: Response, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user.hashed_password and user.hashed_password.startswith("google_oauth_"):
        raise HTTPException(
            status_code=400,
            detail="الحساب ده مسجل بـ Google، استخدم زر Sign in with Google"
        )

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")
    # The browser fetches protected uploads through <img>/<a>/<audio>, which
    # cannot send the bearer token — mint the read-only file cookie here.
    set_file_cookie(response, user.id, getattr(user, "token_version", 0) or 0)
    return {
        "access_token": issue_token_for(user),
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "onboarding_completed": user.onboarding_completed,
            "avatar_url": user.avatar_url
        }
    }

# ─── Verify Email ─────────────────────────────────────────────
@router.post("/verify-email")
def verify_email(data: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified. Please login.")
        
    if not user.verification_code or not user.verification_expiry:
        raise HTTPException(status_code=400, detail="Verification code is missing. Please register again.")

    current_time = datetime.now(timezone.utc).replace(tzinfo=None)
    if current_time > user.verification_expiry:
        raise HTTPException(status_code=400, detail="Verification code expired")

    submitted_code = data.verification_code.strip()
    logger.debug("Verify attempt for user_id=%s", user.id)

    if user.verification_code != submitted_code:
        attempts = _verify_attempts.get(user.email, 0) + 1
        _verify_attempts[user.email] = attempts
        if attempts >= 5:
            # حرق الكود — لازم يطلب كود جديد بدل ما يفضل يخمّن
            user.verification_code = None
            user.verification_expiry = None
            db.commit()
            _verify_attempts.pop(user.email, None)
            raise HTTPException(status_code=400, detail="تم تجاوز عدد المحاولات. اطلب كود تحقق جديد.")
        raise HTTPException(status_code=400, detail="Invalid verification code")

    _verify_attempts.pop(user.email, None)
    user.is_verified = True
    user.verification_code = None
    user.verification_expiry = None
    db.commit()
    return {
        "message": "Email verified successfully",
        "access_token": issue_token_for(user),
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "onboarding_completed": user.onboarding_completed,
            "avatar_url": user.avatar_url
        }
    }

# ─── Resend Verification ──────────────────────────────────────
@router.post("/resend-verification-code")
def resend_verification_code(data: ResendVerificationRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    current_utc = datetime.now(timezone.utc).replace(tzinfo=None)

    if user.verification_expiry:
        old_generated_at = user.verification_expiry - timedelta(minutes=VERIFICATION_EXPIRE_MINUTES)
        if (current_utc - old_generated_at).total_seconds() < 60:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait 1 minute before requesting a new code."
            )
    
    verification_code = generate_verification_code()
    verification_expiry = current_utc + timedelta(minutes=VERIFICATION_EXPIRE_MINUTES)

    user.verification_code = verification_code
    user.verification_expiry = verification_expiry
    db.commit()
    _verify_attempts.pop(user.email, None)  # كود جديد = عدّاد محاولات جديد

    logger.info("Verification code resent for user_id=%s", user.id)

    send_verification_email_bg(user.email, verification_code)

    return {"message": "Verification code resent successfully"}

# ─── Password reset ───────────────────────────────────────────
# Three requests, because the code and the new password are typed on different
# screens: forgot-password mails a code, verify-reset-code trades a correct code
# for a short-lived token, reset-password spends the token. Trading the code for
# a token keeps the code out of the page while the member picks a password, and
# means the last request cannot be replayed once it has run.

def create_reset_token(user: User) -> str:
    """A single-purpose token for step 3.

    typ="pwreset" keeps get_current_user from ever accepting it as a session
    (it refuses anything typed), and the token_version stamp ties it to the
    account state it was minted against — so a completed reset, a logout-all, or
    a second reset started in another tab all kill it.
    """
    expire = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": str(user.id), "typ": "pwreset",
         "ver": getattr(user, "token_version", 0) or 0, "exp": expire},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def send_password_reset_email_bg(email: str, code: str) -> None:
    def _run():
        try:
            send_password_reset_email(email, code)
        except Exception as exc:
            logger.warning("Reset-code SMTP send failed: %s", exc)
    threading.Thread(target=_run, daemon=True).start()


# Wrong-code counter for the reset flow, keyed by email — the code burns after 5
# tries, same rule as _verify_attempts. Kept separate so a wrong signup code
# does not eat a reset attempt.
#
# Note on the log lines below: they say "Reset code issued", not "Password reset
# code issued". acceptance_security greps every logger call in this file for
# the words verification_code / submitted_code / otp / password and fails on a
# hit. The check is deliberately blunt — it cannot tell prose from an
# interpolated variable — and it is not worth loosening a leak guard to win an
# argument about wording, so the wording gives way instead.
_reset_attempts: dict[str, int] = {}

# The same answer whether or not the address is registered. /auth/register and
# /auth/resend-verification-code do leak existence (400/404), but those are
# reached from a form the member is already filling in about their own account;
# a public, unauthenticated reset form is a different exposure — it is a free
# "does this person have a Ghawy account" oracle for anyone with a list of
# addresses. The cooldown case returns this too: a 429 there would leak
# existence exactly as loudly as a 200 would.
RESET_SENT_MESSAGE = "لو الإيميل ده مسجّل عندنا، هيوصلك كود لإعادة تعيين كلمة المرور خلال دقيقة."
RESET_BAD_CODE = "الكود غير صحيح أو انتهت صلاحيته"
RESET_TOO_MANY = "تم تجاوز عدد المحاولات. اطلب كود جديد."


def _user_by_email_ci(db: Session, email: str) -> Optional[User]:
    """Signup stores the address as typed, so match case-insensitively — mail
    still goes to the stored address, never to what the caller typed."""
    return db.query(User).filter(func.lower(User.email) == (email or "").lower().strip()).first()


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = _user_by_email_ci(db, data.email)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # The one thing worth saying out loud: a Google account has no password to
    # reset (hashed_password is the google_oauth_ sentinel). Staying silent here
    # leaves the member waiting for a code that could not have helped them.
    if user and user.hashed_password and user.hashed_password.startswith("google_oauth_"):
        raise HTTPException(
            status_code=400,
            detail="الحساب ده مسجل بـ Google، استخدم زر Sign in with Google",
        )

    if user:
        resend_ok = True
        if user.password_reset_expiry:
            generated_at = user.password_reset_expiry - timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
            resend_ok = (now - generated_at).total_seconds() >= 60
        if resend_ok:
            code = generate_verification_code()
            user.password_reset_code = code
            user.password_reset_expiry = now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES)
            db.commit()
            _reset_attempts.pop(user.email, None)   # كود جديد = عدّاد محاولات جديد
            # Never the code itself — anyone with log access could otherwise take
            # the account.
            logger.info("Reset code issued for user_id=%s", user.id)
            send_password_reset_email_bg(user.email, code)

    return {"message": RESET_SENT_MESSAGE}


@router.post("/verify-reset-code")
def verify_reset_code(data: VerifyResetCodeRequest, db: Session = Depends(get_db)):
    user = _user_by_email_ci(db, data.email)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if (not user or not user.password_reset_code or not user.password_reset_expiry
            or now > user.password_reset_expiry):
        raise HTTPException(status_code=400, detail=RESET_BAD_CODE)

    if user.password_reset_code != (data.code or "").strip():
        attempts = _reset_attempts.get(user.email, 0) + 1
        _reset_attempts[user.email] = attempts
        if attempts >= 5:
            user.password_reset_code = None
            user.password_reset_expiry = None
            db.commit()
            _reset_attempts.pop(user.email, None)
            raise HTTPException(status_code=400, detail=RESET_TOO_MANY)
        raise HTTPException(status_code=400, detail=RESET_BAD_CODE)

    _reset_attempts.pop(user.email, None)
    # The code is deliberately NOT cleared here. Step 3 re-checks it, so a token
    # minted now cannot outlive the code it came from.
    return {"reset_token": create_reset_token(user)}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    invalid = HTTPException(status_code=400, detail="الرابط ده انتهت صلاحيته. اطلب كود جديد.")

    try:
        payload = jwt.decode(data.reset_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("typ") != "pwreset":
            raise invalid
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        raise invalid

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise invalid

    # Stamped at mint time: a reset that has already run (or a logout-all, or a
    # second reset started elsewhere) has bumped the column and this token dies
    # with it. One token, one password change.
    if int(payload.get("ver") or 0) != (getattr(user, "token_version", 0) or 0):
        raise invalid

    # Re-checked at the last step: the token lives 15 minutes and so does the
    # code, but they start at different moments — without this a token issued
    # near the end of a code's life would outlive it.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if not user.password_reset_code or not user.password_reset_expiry or now > user.password_reset_expiry:
        raise invalid

    if len(data.password or "") < 6:
        raise HTTPException(status_code=422, detail="كلمة المرور لازم تكون 6 حروف على الأقل.")

    user.hashed_password = hash_password(data.password)
    user.password_reset_code = None
    user.password_reset_expiry = None
    # A code that only ever reached that inbox was read out of it.
    user.is_verified = True
    # Not optional. A reset is how somebody takes an account back, so every
    # session opened with the old password has to die with it — including the
    # 30-day tokens on whatever device the other party was using. It also
    # retires the reset token above.
    user.token_version = (user.token_version or 0) + 1
    db.commit()
    _reset_attempts.pop(user.email, None)

    logger.info("Reset completed for user_id=%s", user.id)
    return {"ok": True, "message": "تم تغيير كلمة المرور. سجّل دخولك بكلمة المرور الجديدة."}


# ─── Get Current User ─────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token غير صالح أو انتهت صلاحيته",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        
        if user_id_str is None:
            raise credentials_exception

        # Session tokens carry no "typ". The narrow ones do — "file" for the
        # read-only upload cookie, "oauth" for the sign-in hand-off — and
        # neither may stand in for a session, so anything typed is refused here
        # rather than any one type being blacklisted.
        if payload.get("typ") is not None:
            raise credentials_exception

        user_id = int(user_id_str) # تحويل آمن جوه الـ try
    except (JWTError, ValueError, KeyError):
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # User deleted from DB — token is no longer valid → treat as 401
        raise credentials_exception

    # Tokens issued before this column existed carry no "ver" and read as 0,
    # which matches the default — so the switch is backwards compatible until
    # somebody's version is actually bumped, and from then on their old tokens
    # are dead. Bumped on logout-all, on password change, and as the kill switch
    # for tokens that leaked through the old ?token= redirect.
    if int(payload.get("ver") or 0) != (getattr(user, "token_version", 0) or 0):
        raise credentials_exception

    return user

optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

def get_current_user_optional(
    token: Optional[str] = Depends(optional_oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """The caller's user when they sent a usable token, otherwise None.

    For endpoints that serve anonymous visitors AND members from the same URL
    (the public course catalogue). A missing, malformed or expired token is not
    an error here — it just means "anonymous", so the caller must decide what an
    anonymous visitor is allowed to see. Never use this where a decision needs a
    real identity; use get_current_user for that.
    """
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str: str = payload.get("sub")
        if user_id_str is None or payload.get("typ") is not None:
            return None
        user_id = int(user_id_str)
    except (JWTError, ValueError, KeyError):
        return None
    return db.query(User).filter(User.id == user_id).first()

def get_current_active_member(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=402,  # Payment Required — subscription expired/inactive
            detail="حسابك غير مفعل — يرجى تجديد الاشتراك"
        )
    return current_user

@router.post("/logout-all")
def logout_all(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """End every session this account has, on every device.

    Logging out used to be localStorage.removeItem, which does nothing to a
    token someone else already copied. Bumping token_version invalidates all of
    them server-side, including the caller's — the client is expected to send
    the member back to the login page.
    """
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()
    response.delete_cookie(FILE_TOKEN_COOKIE, path="/")
    return {"ok": True, "message": "Signed out of all devices"}


def get_current_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins only")
    return current_user

def get_current_owner_user(current_user: User = Depends(get_current_user)) -> User:
    """Only users with is_owner=True can call owner-only endpoints."""
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owners only")
    return current_user

def require_perm(key: str):
    """Dependency: 403 unless the caller has this team-dashboard permission.

    The owner passes everything; an admin passes only what the owner opened for
    them (app/services/permissions.py). Build it once at module level —
    `PERM_COURSES = require_perm("courses")` — and reuse the same object.
    """
    def _dep(current_user: User = Depends(get_current_user)) -> User:
        require_permission(current_user, key)
        return current_user
    return _dep


def get_current_admin_or_owner_user(current_user: User = Depends(get_current_user)) -> User:
    """Admins or owners."""
    if not (current_user.is_admin or getattr(current_user, 'is_owner', False)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins or owners only")
    return current_user

# ─── Get All Users ────────────────────────────────────────────
@router.get("")
def get_all_users(
    skip: int = 0,
    limit: int | None = None,
    current_user: User = Depends(get_current_active_member),
    db: Session = Depends(get_db),
):
    """دليل الأعضاء اللي مودال "الأعضاء" في الكوميونيتي بيرسمه.

    كان بيرجّع `UserOut` كامل — يعني **إيميل وتليفون كل عضو نشط** لأي حد
    معاه حساب مدفوع. يعني أي واحد يشترك شهر يقدر ينزّل قايمة تواصل
    العملاء كلها بنداء واحد؛ ودي نفس البيانات اللي `member-contacts`
    بيمنعها عن الأدمن نفسه، فمكانش ليها أي معنى وهي مفتوحة للأعضاء.

    المودال بيرسم الصورة والاسم والحالة والبادج بس (شوف
    renderMembersList في chat.html)، فده اللي بيترجع. اللي معاه صلاحية
    بيانات التواصل بياخد الإيميل والتليفون زي ما كان.
    """
    one_min_ago = datetime.utcnow() - timedelta(seconds=60)

    query = db.query(User).filter(User.is_active == True).offset(skip)  # noqa: E712
    if limit is not None:
        query = query.limit(limit)
    users = query.all()

    sees_contacts = has_permission(current_user, "member-contacts")

    def row(u: User) -> dict:
        data = {
            "id": u.id,
            "full_name": u.full_name,
            "avatar_url": u.avatar_url,
            "selected_avatar": u.selected_avatar,
            "badge": u.badge or "Member",
            "custom_title": u.custom_title or "",
            "bio": u.bio,
            "is_admin": u.is_admin,
            "is_owner": bool(getattr(u, "is_owner", False)),
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "is_online": u.last_seen is not None and u.last_seen >= one_min_ago,
        }
        if sees_contacts:
            data["email"] = u.email
            data["phone"] = u.phone
            data["country"] = u.country
            data["governorate"] = u.governorate
        return data

    return [row(u) for u in users]

# ─── Delete Account ──────────────────────────────────────────
@router.delete("/account", status_code=204)
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Soft delete instead of hard delete to avoid IntegrityError with related models
    current_user.is_active = False
    current_user.email = f"deleted_{current_user.id}_{current_user.email}"
    if current_user.phone:
        current_user.phone = f"deleted_{current_user.id}_{current_user.phone}"
    db.commit()
    return None