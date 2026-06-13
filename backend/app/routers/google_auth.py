# google_auth.py
from fastapi import APIRouter, Request, Depends
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
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
    redirect_uri = "http://127.0.0.1:8000/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get("/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')
    
    email = user_info['email']
    name = user_info.get('name', '')
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else ""
            
        country = ""
        governorate = ""
        
        try:
            url = f"https://ipapi.co/{ip}/json/" if ip and ip not in ["127.0.0.1", "localhost", "::1"] else "https://ipapi.co/json/"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3.0) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    country = data.get("country_name", "")
                    governorate = data.get("city", "") or data.get("region", "")
        except Exception:
            pass

        # Fallback to ip-api.com if first API fails or returns empty
        if not country:
            try:
                url_fb = f"http://ip-api.com/json/{ip}" if ip and ip not in ["127.0.0.1", "localhost", "::1"] else "http://ip-api.com/json/"
                req_fb = urllib.request.Request(url_fb, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_fb, timeout=3.0) as response:
                    if response.status == 200:
                        data_fb = json.loads(response.read().decode())
                        country = data_fb.get("country", "")
                        governorate = data_fb.get("city", "") or data_fb.get("regionName", "")
            except Exception:
                pass

        # Ultimate fallback
        if not country:
            country = "Egypt"
        if not governorate:
            governorate = "Unknown"

        user = User(
            full_name=name,
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
    
    frontend_url = "http://127.0.0.1:5500"
    if not user.is_active:
        return RedirectResponse(f"{frontend_url}/payment.html?token={access_token}")
        
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
    new_user = User(
        full_name=req.full_name,
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