"""
Manual Payment Requests — Instapay flow.
Public endpoints for submission + Admin endpoints for review/approve/reject.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy.sql import func as sql_func
from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets
import logging
import os
import uuid
import aiofiles
from pathlib import Path
from pydantic import BaseModel

import httpx
from app.database import get_db
from app.models import User, ManualPaymentRequest, Payment, PaymentMethod, PaymentStatus
from app.routers.users import get_current_user
from app.services.payment_service import to_cairo_iso, CAIRO_TZ
from app.services.email_service import (
    send_admin_payment_notification,
    send_payment_approval_email,
    send_payment_rejection_email,
)

PAYMENT_WEBHOOK_URL = os.getenv("N8N_PAYMENT_WEBHOOK_URL")


async def _send_payment_webhook(payload: dict):
    if not PAYMENT_WEBHOOK_URL:
        logger.warning("⚠️ N8N_PAYMENT_WEBHOOK_URL not configured — skipping notification")
        return
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(PAYMENT_WEBHOOK_URL, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info("✅ Payment webhook sent successfully")
    except Exception as e:
        logger.error("❌ Failed to send payment webhook: %s", e)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manual-payments", tags=["Manual Payments"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
RECEIPTS_DIR = BACKEND_DIR / "uploads" / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_RECEIPT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_RECEIPT_SIZE = 5 * 1024 * 1024  # 5 MB


def _sniff_receipt_type(content: bytes) -> Optional[str]:
    """Return a safe extension based on the file's actual magic bytes, or None
    if the bytes are not a genuine allowed image/PDF. The browser-supplied
    Content-Type and the original filename are NEVER trusted for what we store:
    an SVG/HTML/script renamed to .png or given a fake MIME must be rejected
    here so it can never land on disk with an executable extension."""
    if content[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    if content[:5] == b"%PDF-":
        return ".pdf"
    return None

# Subscription length granted on approval, per plan.
PLAN_DURATION_DAYS = {"monthly": 30, "quarterly": 90, "yearly": 365}
DEFAULT_PLAN = "monthly"

# Fallback EGP price per plan when the member didn't state an amount.
# Mirrors PLANS.EGP in frontend/src/js/pricing.js — the yearly plan moved from
# 4000 to 3500 and this was still recording the old figure on any submission
# that arrived without an amount.
PLAN_DEFAULT_AMOUNT_EGP = {"monthly": 600, "quarterly": 1200, "yearly": 3500}


def _record_manual_payment(db: Session, req: ManualPaymentRequest, user: User, when: datetime):
    """Create a CONFIRMED manual Payment row so the approval shows in the Payments tab.

    Idempotent: skips if a manual payment for this request already exists.
    """
    provider_order_id = f"manual-{req.id}"
    existing = db.query(Payment).filter(
        Payment.method == PaymentMethod.MANUAL,
        Payment.provider_order_id == provider_order_id,
    ).first()
    if existing:
        return existing

    plan = (req.plan or DEFAULT_PLAN).lower()
    amount = float(req.amount) if req.amount else PLAN_DEFAULT_AMOUNT_EGP.get(plan, 600)
    payment = Payment(
        user_id=user.id,
        method=PaymentMethod.MANUAL,
        status=PaymentStatus.CONFIRMED,
        amount=amount,
        currency="EGP",
        provider_order_id=provider_order_id,
        plan_key=f"{plan}_egp",
        created_at=req.created_at or when,
        confirmed_at=when,
    )
    db.add(payment)
    return payment


# ── Helper ─────────────────────────────────────────────────
def require_admin(current_user: User):
    """Raise 403 if the current user is neither an admin nor an owner."""
    if not (getattr(current_user, 'is_admin', False) or getattr(current_user, 'is_owner', False)):
        raise HTTPException(status_code=403, detail="Admins only")


def require_owner(current_user: User):
    """Raise 403 if the current user is not an owner (Pending Requests is owner-only)."""
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")


def _request_to_dict(req: ManualPaymentRequest) -> dict:
    """Convert a ManualPaymentRequest to a JSON-safe dict."""
    return {
        "id": req.id,
        "full_name": req.full_name,
        "email": req.email,
        "phone": req.phone,
        "amount": float(req.amount) if req.amount else None,
        "plan": req.plan,
        "notes": req.notes,
        "receipt_url": req.receipt_url,
        "status": req.status,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "invite_sent_at": req.invite_sent_at.isoformat() if req.invite_sent_at else None,
        "invite_expires_at": req.invite_expires_at.isoformat() if req.invite_expires_at else None,
        "rejection_reason": req.rejection_reason,
        "reviewed_by": req.reviewed_by,
        "reviewed_at": req.reviewed_at.isoformat() if req.reviewed_at else None,
    }


# ══════════════════════════════════════════════════════════
#  WHO MAY OPEN A NEW REQUEST
# ══════════════════════════════════════════════════════════
#
# Two rules stop a second receipt from being uploaded:
#
#   - an open request. One review at a time — uploading again while the first
#     is still pending only hands the reviewer two screenshots of the same
#     transfer, and the member sits there expecting two subscriptions.
#   - a subscription that has not run out yet. Paying again for a month you
#     already own is the mistake this exists to prevent.
#
# The second rule has one deliberate exception. A member who came from
# /renewal to renew early arrives at /pay with `intent=renew`, and must get
# through — otherwise Instapay is closed to everyone whose subscription is
# still alive, which is precisely the group renewing. The flag is
# client-supplied and so forgeable, but forging it buys nothing: the
# open-request rule above is unconditional, so the most a forged renew can do
# is submit the one request the member could have submitted from /renewal
# anyway.
#
# The messages are Arabic because the pages that surface them are. The
# frontend does not depend on the wording — /pay reads `reason` from
# /my-status and renders its own bilingual panel — so these are the fallback
# for anything that only shows `detail`.

RENEW_INTENT = "renew"

BLOCK_MESSAGES = {
    "pending": "عندك طلب دفع مسجّل بالفعل ولسه تحت المراجعة. استنى الموافقة الأول.",
    "active": "اشتراكك لسه شغال، فمش محتاج ترفع طلب جديد. لو عايز تجدد بدري ادخل من صفحة التجديد.",
}


def _open_request(db: Session, email: str) -> Optional[ManualPaymentRequest]:
    """The member's still-pending request, if they have one."""
    return db.query(ManualPaymentRequest).filter(
        ManualPaymentRequest.email == email,
        ManualPaymentRequest.status == "pending",
    ).order_by(ManualPaymentRequest.created_at.desc()).first()


def _submission_state(db: Session, user: User, intent: Optional[str] = None) -> dict:
    """Whether `user` may open a manual payment request, and if not, why.

    Shared by /submit (which enforces it) and /my-status (which lets /pay show
    the reason instead of the upload form), so the two can never disagree.
    """
    pending = _open_request(db, user.email)
    if pending:
        return {
            "can_submit": False,
            "reason": "pending",
            "request_id": pending.id,
            "request_ref": f"MANUAL-{pending.id}",
            "submitted_at": to_cairo_iso(pending.created_at),
            "end_at": to_cairo_iso(user.end_at),
        }

    renewing = (intent or "").strip().lower() == RENEW_INTENT
    if user.is_active and not renewing:
        return {
            "can_submit": False,
            "reason": "active",
            "request_id": None,
            "request_ref": None,
            "submitted_at": None,
            "end_at": to_cairo_iso(user.end_at),
        }

    return {
        "can_submit": True,
        "reason": None,
        "request_id": None,
        "request_ref": None,
        "submitted_at": None,
        "end_at": to_cairo_iso(user.end_at),
    }


# ══════════════════════════════════════════════════════════
#  PUBLIC ENDPOINTS (no auth)
# ══════════════════════════════════════════════════════════

@router.post("/submit")
async def submit_payment_request(
    amount: Optional[float] = Form(None),
    plan: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    intent: Optional[str] = Form(None),
    receipt: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a manual payment request with receipt screenshot."""
    email = current_user.email
    full_name = current_user.full_name
    phone = current_user.phone

    # Already has an open request, or an unexpired subscription — see the
    # comment above _submission_state for the renew exception.
    state = _submission_state(db, current_user, intent)
    if not state["can_submit"]:
        raise HTTPException(status_code=409, detail=BLOCK_MESSAGES[state["reason"]])

    # Validate receipt file. The declared Content-Type is a first cheap gate,
    # but it is client-supplied and trivially spoofed, so the real check is the
    # magic-byte sniff below — that is what decides the stored extension.
    content_type = receipt.content_type or ""
    if content_type not in ALLOWED_RECEIPT_TYPES:
        raise HTTPException(status_code=422, detail="Receipt must be JPG, PNG, WebP or PDF")

    content = await receipt.read()
    if len(content) > MAX_RECEIPT_SIZE:
        raise HTTPException(status_code=422, detail="Receipt file too large. Max 5MB.")

    ext = _sniff_receipt_type(content)
    if ext is None:
        raise HTTPException(status_code=422, detail="Receipt must be a real JPG, PNG, WebP or PDF")

    # Save receipt under a fully server-generated name. The attacker-controlled
    # original filename is discarded entirely so a disguised extension such as
    # evil.svg or x.php.jpg can never reach disk or be served back as active
    # content.
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = RECEIPTS_DIR / unique_name
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    receipt_url = f"/uploads/receipts/{unique_name}"

    # Normalize the plan to a known value (defaults to monthly).
    normalized_plan = (plan or "").strip().lower()
    if normalized_plan not in PLAN_DURATION_DAYS:
        normalized_plan = DEFAULT_PLAN

    # Create request
    mpr = ManualPaymentRequest(
        full_name=full_name,
        email=email,
        phone=phone,
        receipt_url=receipt_url,
        amount=amount,
        plan=normalized_plan,
        notes=notes.strip() if notes else None,
        status="pending",
    )
    db.add(mpr)
    db.commit()
    db.refresh(mpr)

    # Send admin notification email (non-blocking)
    try:
        send_admin_payment_notification(
            full_name=mpr.full_name,
            email=mpr.email,
            phone=mpr.phone,
            amount=mpr.amount,
            created_at=mpr.created_at.replace(tzinfo=timezone.utc).astimezone(CAIRO_TZ).strftime("%Y-%m-%d %H:%M") if mpr.created_at else "N/A",
        )
    except Exception as exc:
        logger.warning("Failed to send admin notification email: %s", exc)

    # Send n8n webhook notification (non-blocking)
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    webhook_payload = {
        "event": "payment_submitted",
        "full_name": mpr.full_name,
        "email": mpr.email,
        "phone": mpr.phone or "",
        "amount": float(mpr.amount) if mpr.amount else None,
        "notes": mpr.notes or "",
        "receipt_url": f"{frontend_url}{mpr.receipt_url}",
        "submitted_at": to_cairo_iso(mpr.created_at),
        "review_url": f"{frontend_url}/teamdashboard.html#pending-requests",
    }
    import asyncio
    asyncio.create_task(_send_payment_webhook(webhook_payload))

    return {
        "id": mpr.id,
        "status": "pending",
        "message": "Request submitted successfully",
        # The success screen tells the member which inbox the confirmation is
        # going to. It has to be the address the request was actually filed
        # under — the one taken from the token above, never anything typed on
        # the page — so it is returned from here rather than guessed.
        "email": mpr.email,
    }


@router.get("/my-status")
def my_submission_status(
    intent: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Can the signed-in member open a manual request right now?

    /pay calls this before drawing the upload form: if the answer is no, it
    shows the reason (an open request and its number, or a subscription that
    has not run out) instead of letting someone upload a receipt that /submit
    would only reject afterwards.

    Authenticated on purpose. The neighbouring /status/{email} takes an
    address from anyone; this one carries a request id and a subscription
    expiry, so it answers only about the caller.
    """
    state = _submission_state(db, current_user, intent)
    state["email"] = current_user.email
    return state


@router.get("/status/{email}")
def check_request_status(email: str, db: Session = Depends(get_db)):
    """Check status of a submitted payment request by email."""
    email = email.strip().lower()
    request = db.query(ManualPaymentRequest).filter(
        ManualPaymentRequest.email == email,
    ).order_by(ManualPaymentRequest.created_at.desc()).first()

    if not request:
        raise HTTPException(status_code=404, detail="No payment request found for this email")

    result = {"status": request.status}
    if request.status == "rejected" and request.rejection_reason:
        result["rejection_reason"] = request.rejection_reason
    return result


# ══════════════════════════════════════════════════════════
#  ADMIN ENDPOINTS (protected)
# ══════════════════════════════════════════════════════════

@router.get("/stats")
def get_manual_payment_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stats summary for dashboard badge."""
    require_admin(current_user)  # 🔒 admins + owners

    pending_count = db.query(sql_func.count(ManualPaymentRequest.id)).filter(
        ManualPaymentRequest.status == "pending"
    ).scalar()

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    approved_today = db.query(sql_func.count(ManualPaymentRequest.id)).filter(
        ManualPaymentRequest.status == "approved",
        ManualPaymentRequest.reviewed_at >= today_start,
    ).scalar()

    rejected_total = db.query(sql_func.count(ManualPaymentRequest.id)).filter(
        ManualPaymentRequest.status == "rejected"
    ).scalar()

    return {
        "pending_count": pending_count,
        "approved_today": approved_today,
        "rejected_total": rejected_total,
    }


@router.get("")
def list_payment_requests(
    status: str = Query("pending"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all payment requests (admin only)."""
    require_admin(current_user)  # 🔒 admins + owners

    query = db.query(ManualPaymentRequest)

    if status != "all":
        query = query.filter(ManualPaymentRequest.status == status)

    total = query.count()
    pages = max(1, (total + limit - 1) // limit)

    requests = query.order_by(
        ManualPaymentRequest.created_at.desc()
    ).offset((page - 1) * limit).limit(limit).all()

    # Count by status
    pending_count = db.query(sql_func.count(ManualPaymentRequest.id)).filter(
        ManualPaymentRequest.status == "pending"
    ).scalar()
    approved_count = db.query(sql_func.count(ManualPaymentRequest.id)).filter(
        ManualPaymentRequest.status == "approved"
    ).scalar()
    rejected_count = db.query(sql_func.count(ManualPaymentRequest.id)).filter(
        ManualPaymentRequest.status == "rejected"
    ).scalar()

    return {
        "requests": [_request_to_dict(r) for r in requests],
        "total": total,
        "page": page,
        "pages": pages,
        "counts": {
            "pending": pending_count,
            "approved": approved_count,
            "rejected": rejected_count,
        },
    }


@router.get("/{request_id}")
def get_payment_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get single request detail (admin only)."""
    require_admin(current_user)  # 🔒 admins + owners

    req = db.query(ManualPaymentRequest).filter(ManualPaymentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    return _request_to_dict(req)


@router.post("/{request_id}/approve")
def approve_request(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Approve a payment request and activate user account."""
    require_admin(current_user)  # 🔒 admins + owners

    req = db.query(ManualPaymentRequest).filter(ManualPaymentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    now = datetime.utcnow()

    req.status = "approved"
    req.reviewed_by = current_user.id
    req.reviewed_at = now
    
    # Activate the user with a 30-day subscription from approval date
    user = db.query(User).filter(User.email == req.email).first()
    if user:
        user.is_active = True
        user.is_verified = True
        user.subscription_source = "manual_payment"
        # Subscription length follows the plan chosen at submission (defaults to monthly/30d).
        plan_days = PLAN_DURATION_DAYS.get(req.plan or DEFAULT_PLAN, 30)
        # Always extend from now (approval time), not from previous end_at
        user.end_at = now + timedelta(days=plan_days)

        # Record a confirmed manual Payment so it appears in the Payments tab
        # (filterable by the "manual" method) and in revenue analytics.
        _record_manual_payment(db, req, user, now)

    db.commit()

    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    login_url = f"{frontend_url}/login.html"

    import urllib.parse
    def format_phone_for_whatsapp(phone: str) -> str:
        if not phone: return ""
        # Remove spaces, dashes, plus signs
        phone = phone.replace(" ", "").replace("-", "").replace("+", "")
        # If starts with 0 (Egyptian number like 01019381981), replace with country code
        if phone.startswith("0"):
            phone = "20" + phone[1:]
        return phone

    whatsapp_message = (
        f"مرحباً {req.full_name} 👋\n\n"
        f"تم التحقق من دفعتك بنجاح! 🎉\n\n"
        f"تم تفعيل حسابك، وتقدر تدخل على المنصة دلوقتي من الرابط التالي:\n"
        f"{login_url}\n\n"
        f"نتمنى لك تجربة ممتعة!"
    )

    whatsapp_url = None
    if req.phone:
        formatted_phone = format_phone_for_whatsapp(req.phone)
        whatsapp_url = f"https://wa.me/{formatted_phone}?text={urllib.parse.quote(whatsapp_message)}"

    # We can also send an email here if we want (e.g. send_payment_approval_email)
    # The previous implementation sent an invite link, we can update the email template to send activation info instead.
    try:
        send_payment_approval_email(
            to_email=req.email,
            full_name=req.full_name,
            registration_url=login_url,  # Reuse parameter but pass login URL
        )
    except Exception as exc:
        logger.warning("Failed to send activation email to %s: %s", req.email, exc)

    return {
        "message": "approved",
        "login_url": login_url,
        "whatsapp_url": whatsapp_url
    }


class RejectBody(BaseModel):
    reason: str


@router.post("/{request_id}/reject")
def reject_request(
    request_id: int,
    body: RejectBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reject a payment request with a reason."""
    require_admin(current_user)  # 🔒 admins + owners

    req = db.query(ManualPaymentRequest).filter(ManualPaymentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    now = datetime.utcnow()
    req.status = "rejected"
    req.rejection_reason = body.reason
    req.reviewed_by = current_user.id
    req.reviewed_at = now
    db.commit()

    # Send rejection email
    try:
        send_payment_rejection_email(
            to_email=req.email,
            full_name=req.full_name,
            rejection_reason=body.reason,
        )
    except Exception as exc:
        logger.warning("Failed to send rejection email to %s: %s", req.email, exc)

    return {"message": "rejected"}


@router.post("/{request_id}/resend-invite")
def resend_invite(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Resend activation notification."""
    require_admin(current_user)  # 🔒 admins + owners

    req = db.query(ManualPaymentRequest).filter(ManualPaymentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "approved":
        raise HTTPException(status_code=400, detail="Can only resend notification for approved requests")

    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    login_url = f"{frontend_url}/login.html"

    try:
        send_payment_approval_email(
            to_email=req.email,
            full_name=req.full_name,
            registration_url=login_url,
        )
    except Exception as exc:
        logger.warning("Failed to resend activation email to %s: %s", req.email, exc)

    return {"message": "notification resent", "login_url": login_url}
