# google_auth.py
from fastapi import APIRouter, Request, Depends, Response, HTTPException
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
from urllib.parse import quote
from pydantic import BaseModel
from ..routers.users import (
    OAUTH_HANDOFF_COOKIE, set_handoff_cookie, read_handoff_token,
    set_file_cookie, create_token as create_session_token,
)
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

    # Google will happily return an address the account has not proven it owns.
    # Accounts here are keyed on email — an unverified one could be used to
    # claim an existing member's account on a provider that allows it — so the
    # claim has to say so.
    if not user_info.get('email_verified'):
        return RedirectResponse("https://ghawy.ai/login?error=email_unverified")
    
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
    
    frontend_url = "https://ghawy.ai"
    if not user.is_active:
        # Signed in but not subscribed → the plans page.
        destination = "/pricing"
    elif not user.onboarding_completed:
        destination = "/onboarding.html"
    else:
        destination = "/dashboard.html"

    # No token in the URL. These three pages load GTM, GA4, the Meta Pixel and
    # Clarity in <head>, all of which read location.href on load, so a token in
    # the query string was a member's 30-day session handed to three third
    # parties (plus nginx's access log, browser history and Referer). The
    # session travels in a 120-second HttpOnly cookie instead, and
    # /auth-complete — a bare page with no analytics on it — swaps that for the
    # real token over a same-origin POST before forwarding here.
    response = RedirectResponse(
        f"{frontend_url}/auth-complete?next={quote(destination, safe='/')}"
    )
    set_handoff_cookie(response, user.id)
    return response


class ExchangeOut(BaseModel):
    access_token: str


@router.post("/auth/exchange")
def exchange_handoff(response: Response, request: Request, db: Session = Depends(get_db)):
    """Swap the sign-in hand-off cookie for the session token.

    Single-use: the cookie is cleared on the way out, so even if the 120-second
    window is still open the code cannot be spent twice.
    """
    user_id = read_handoff_token(request.cookies.get(OAUTH_HANDOFF_COOKIE))
    response.delete_cookie(OAUTH_HANDOFF_COOKIE, path="/")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Sign-in link expired — please sign in again")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Sign-in link expired — please sign in again")

    set_file_cookie(response, user.id)
    return {
        "access_token": create_session_token(user.id, getattr(user, "token_version", 0) or 0),
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "onboarding_completed": user.onboarding_completed,
            "avatar_url": user.avatar_url,
        },
    }

# The invite-token flow lived here and has been removed.
#
# GET /auth/invite/{token} and POST /auth/register-with-invite read
# ManualPaymentRequest.invite_token, but nothing in the codebase has ever
# ASSIGNED that column — approving a manual payment does not mint a token — so
# neither endpoint could be reached by any real invite. What they were was an
# unauthenticated pair that, given a token, created a verified and active user
# with a caller-chosen password and wrote a CONFIRMED payment row.
#
# The columns (invite_token, invite_sent_at, invite_expires_at) are left in
# place. If the flow is ever finished, mint the token with
# secrets.token_urlsafe(32) at approval time, store its hash rather than the
# token, and honour invite_expires_at on both ends.
