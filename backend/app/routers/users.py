# users.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from app.models import User
from app.schemas import UserRegister, UserLogin, UserOut, Token, VerifyEmailRequest, ResendVerificationRequest
from app.database import get_db
import os
import random
import logging
from pathlib import Path
from dotenv import load_dotenv
from app.services.email_service import send_verification_email

logger = logging.getLogger(__name__)

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is required")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days
VERIFICATION_EXPIRE_MINUTES = 15

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except UnknownHashError:
        return False

def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def generate_verification_code() -> str:
    return f"{random.randint(0, 999999):06d}"

# ─── Register ────────────────────────────────────────────────
@router.post("/register", response_model=UserOut, status_code=201)
def register(data: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == data.email).first()

    verification_code = generate_verification_code()
    verification_expiry = datetime.utcnow() + timedelta(minutes=VERIFICATION_EXPIRE_MINUTES)

    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="الإيميل ده موجود بالفعل")

        existing_user.full_name = data.full_name
        existing_user.hashed_password = hash_password(data.password)
        existing_user.phone = data.phone
        existing_user.country = data.country
        existing_user.governorate = data.governorate
        existing_user.verification_code = verification_code
        existing_user.verification_expiry = verification_expiry
        user = existing_user
    else:
        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hash_password(data.password),
            phone=data.phone,
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

    logger.info("📧 Verification code for %s: %s", user.email, verification_code)

    try:
        send_verification_email(user.email, verification_code)
    except Exception as exc:
        logger.warning("SMTP send failed for %s: %s", user.email, exc)

    return user

# ─── Login ───────────────────────────────────────────────────
@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    # ✅ Google users لازم يسجلوا بـ Google مش بـ password
    if user and user.hashed_password.startswith("google_oauth_"):
        raise HTTPException(
            status_code=400,
            detail="الحساب ده مسجل بـ Google، استخدم زر Sign in with Google"
        )

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="إيميل أو باسورد غلط")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")
    return {"access_token": create_token(user.id)}

# ─── Token (Swagger) ─────────────────────────────────────────
@router.post("/token", response_model=Token)
def token_login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email first")
    return {"access_token": create_token(user.id)}

# ─── Verify Email ─────────────────────────────────────────────
@router.post("/verify-email")
def verify_email(data: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        return {"message": "Email already verified"}
    if not user.verification_code or not user.verification_expiry:
        raise HTTPException(status_code=400, detail="Verification code is missing. Please register again.")
    if datetime.utcnow() > user.verification_expiry:
        raise HTTPException(status_code=400, detail="Verification code expired")

    submitted_code = data.verification_code.strip()
    logger.debug("Verify attempt: email=%s, submitted=%r, stored=%r", data.email, submitted_code, user.verification_code)

    if user.verification_code != submitted_code:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    user.is_verified = True
    user.verification_code = None
    user.verification_expiry = None
    db.commit()
    return {"message": "Email verified successfully"}

# ─── Resend Verification ──────────────────────────────────────
@router.post("/resend-verification-code")
def resend_verification_code(data: ResendVerificationRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    verification_code = generate_verification_code()
    verification_expiry = datetime.utcnow() + timedelta(minutes=VERIFICATION_EXPIRE_MINUTES)
    user.verification_code = verification_code
    user.verification_expiry = verification_expiry
    db.commit()

    logger.info("📧 Resent verification code for %s: %s", user.email, verification_code)

    try:
        send_verification_email(user.email, verification_code)
    except Exception as exc:
        logger.warning("SMTP send failed for %s: %s", user.email, exc)

    return {"message": "Verification code resent successfully"}

# ─── Get Current User ─────────────────────────────────────────
from jose import JWTError

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Token غير صالح")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="المستخدم مش موجود")
    return user


# ─── Get All Users (Community Members) ───────────────────────
@router.get("", response_model=list[UserOut])
def get_all_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    users = db.query(User).all()
    return users


# ─── Delete Account ──────────────────────────────────────────
@router.delete("/account", status_code=204)
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.delete(current_user)
    db.commit()
    return None