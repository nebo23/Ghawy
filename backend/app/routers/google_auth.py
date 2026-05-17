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
            is_active=True
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
    return RedirectResponse(f"{frontend_url}/dashboard.html?token={access_token}")