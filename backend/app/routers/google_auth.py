# google_auth.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..services.name_utils import split_full_name, clean_display_name
from ..services.disposable_emails import is_disposable_email, is_fake_email_pattern
import os, secrets
from jose import jwt
from datetime import datetime, timedelta
import urllib.request
import json
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

router = APIRouter()

oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)

@router.get("/auth/google/login")
async def google_login(request: Request):
    redirect_uri = "https://ghawy.ai/api/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')
    
    email = user_info['email']
    name = user_info.get('name', '')
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Same fake-signup filter as /auth/register — a Google account is no
        # guarantee of a real member (test@gmail.com signs in just fine).
        # Only brand-new signups are checked; existing users are never re-tested.
        if is_disposable_email(email) or is_fake_email_pattern(email):
            return RedirectResponse("https://ghawy.ai/register.html?error=fake_email")

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else ""
            
        # Geo-lookup uses blocking urlopen (up to 2×3s) — run it in a thread so
        # it can't stall the single-worker event loop
        def _geo_lookup(ip_addr: str):
            c, g = "", ""
            try:
                url = f"https://ipapi.co/{ip_addr}/json/" if ip_addr and ip_addr not in ["127.0.0.1", "localhost", "::1"] else "https://ipapi.co/json/"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode())
                        c = data.get("country_name", "")
                        g = data.get("city", "") or data.get("region", "")
            except Exception:
                pass
            if not c:
                try:
                    url_fb = f"http://ip-api.com/json/{ip_addr}" if ip_addr and ip_addr not in ["127.0.0.1", "localhost", "::1"] else "http://ip-api.com/json/"
                    req_fb = urllib.request.Request(url_fb, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req_fb, timeout=3.0) as response:
                        if response.status == 200:
                            data_fb = json.loads(response.read().decode())
                            c = data_fb.get("country", "")
                            g = data_fb.get("city", "") or data_fb.get("regionName", "")
                except Exception:
                    pass
            return c, g

        from fastapi.concurrency import run_in_threadpool
        country, governorate = await run_in_threadpool(_geo_lookup, ip)

        # Ultimate fallback
        if not country:
            country = "Egypt"
        if not governorate:
            governorate = "Unknown"

        # Google's display name is user-chosen text like any other; it lands in
        # the same innerHTML sites as a self-registered name.
        name = clean_display_name(name)
        google_first, google_last = split_full_name(name)
        user = User(
            full_name=name,
            first_name=google_first,
            last_name=google_last,
            email=email,
            hashed_password="google_oauth_" + secrets.token_hex(16),
            phone=None,
            country=country,
            governorate=governorate,
            is_verified=True,
            is_active=False
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    expire = datetime.utcnow() + timedelta(minutes=60 * 24 * 30)  # 30 days
    access_token = jwt.encode(
        {"sub": str(user.id), "exp": expire},
        os.getenv('SECRET_KEY'),
        algorithm="HS256"
    )
    
    frontend_url = "https://ghawy.ai"
    if not user.is_active:
        # Signed in but not subscribed → the plans page. /pricing replaced
        # /payment; utils.js picks the token out of the query there exactly as
        # it did on the old page, so the visitor arrives logged in.
        return RedirectResponse(f"{frontend_url}/pricing?token={access_token}")
        
    if not user.onboarding_completed:
        return RedirectResponse(f"{frontend_url}/onboarding.html?token={access_token}")
        
    return RedirectResponse(f"{frontend_url}/dashboard.html?token={access_token}")

# ══════════════════════════════════════════════════════════
#  INVITE TOKEN ENDPOINTS (Manual Payment Flow)
# ══════════════════════════════════════════════════════════

from pydantic import BaseModel, EmailStr
from ..models import ManualPaymentRequest, Payment
from fastapi import HTTPException
from ..routers.users import create_token, hash_password

class InviteRegisterReq(BaseModel):
    token: str
    password: str

@router.get("/auth/invite/{token}")
def check_invite_token(token: str, db: Session = Depends(get_db)):
    """Validate invite token before showing register page."""
    req = db.query(ManualPaymentRequest).filter(
        ManualPaymentRequest.invite_token == token
    ).first()
    
    if not req:
        raise HTTPException(status_code=404, detail="Invalid token")
    if req.status != "approved":
        raise HTTPException(status_code=400, detail="Request not approved")
    
    now = datetime.utcnow()
    if not req.invite_expires_at or now > req.invite_expires_at:
        raise HTTPException(status_code=410, detail="Token expired. Please contact support.")
        
    return {
        "valid": True,
        "email": req.email,
        "full_name": req.full_name
    }

@router.post("/auth/register-with-invite")
def register_with_invite(data: InviteRegisterReq, db: Session = Depends(get_db)):
    """Register a new user using a valid invite token."""
    req = db.query(ManualPaymentRequest).filter(
        ManualPaymentRequest.invite_token == data.token
    ).first()
    
    if not req or req.status != "approved":
        raise HTTPException(status_code=400, detail="Invalid or unapproved token")
        
    now = datetime.utcnow()
    if not req.invite_expires_at or now > req.invite_expires_at:
        raise HTTPException(status_code=410, detail="Token expired")
        
    # Check if user already exists
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Create User
    invite_first, invite_last = split_full_name(req.full_name)
    new_user = User(
        full_name=req.full_name,
        first_name=invite_first,
        last_name=invite_last,
        email=req.email,
        hashed_password=hash_password(data.password),
        phone=req.phone,
        is_active=True,
        is_verified=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Create Payment record for the manual payment
    payment = Payment(
        user_id=new_user.id,
        method="manual",
        status="confirmed",
        amount=req.amount or 0,
        currency="EGP",
        provider_order_id=f"MANUAL-{req.id}"
    )
    db.add(payment)
    
    # Invalidate token
    req.invite_token = None
    db.commit()
    
    # Return JWT
    return {
        "access_token": create_token(new_user.id),
        "user": {
            "id": new_user.id,
            "email": new_user.email,
            "full_name": new_user.full_name,
            "has_completed_onboarding": new_user.onboarding_completed,
            "avatar_url": new_user.avatar_url
        }
    }
