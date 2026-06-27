"""
Manual Payment Requests — Instapay flow.
Public endpoints for submission + Admin endpoints for review/approve/reject.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy.sql import func as sql_func
from datetime import datetime, timedelta
from typing import Optional
import secrets
import logging
import os
import uuid
import aiofiles
from pathlib import Path
from pydantic import BaseModel

from app.database import get_db
from app.models import User, ManualPaymentRequest
from app.routers.users import get_current_user
from app.services.email_service import (
    send_admin_payment_notification,
    send_payment_approval_email,
    send_payment_rejection_email,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manual-payments", tags=["Manual Payments"])

BACKEND_DIR = Path(__file__).resolve().parents[2]
RECEIPTS_DIR = BACKEND_DIR / "uploads" / "receipts"
RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_RECEIPT_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_RECEIPT_SIZE = 5 * 1024 * 1024  # 5 MB


# ── Helper ─────────────────────────────────────────────────
def require_admin(current_user: User):
    """Raise 403 if the current user is not an admin."""
    if not current_user.is_admin:
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
#  PUBLIC ENDPOINTS (no auth)
# ══════════════════════════════════════════════════════════

@router.post("/submit")
async def submit_payment_request(
    amount: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
    receipt: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a manual payment request with receipt screenshot."""
    email = current_user.email
    full_name = current_user.full_name
    phone = current_user.phone

    # Check for existing pending request
    existing_request = db.query(ManualPaymentRequest).filter(
        ManualPaymentRequest.email == email,
        ManualPaymentRequest.status == "pending",
    ).first()
    if existing_request:
        raise HTTPException(
            status_code=409,
            detail="A pending payment request already exists for this email. Please wait for approval.",
        )

    # Validate receipt file
    content_type = receipt.content_type or ""
    if content_type not in ALLOWED_RECEIPT_TYPES:
        raise HTTPException(status_code=422, detail="Receipt must be JPG, PNG, WebP or PDF")

    content = await receipt.read()
    if len(content) > MAX_RECEIPT_SIZE:
        raise HTTPException(status_code=422, detail="Receipt file too large. Max 5MB.")

    # Save receipt
    ext = Path(receipt.filename or "receipt").suffix or ".jpg"
    unique_name = f"{uuid.uuid4().hex}_{receipt.filename or 'receipt'}"
    file_path = RECEIPTS_DIR / unique_name
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    receipt_url = f"/uploads/receipts/{unique_name}"

    # Create request
    mpr = ManualPaymentRequest(
        full_name=full_name,
        email=email,
        phone=phone,
        receipt_url=receipt_url,
        amount=amount,
        notes=notes.strip() if notes else None,
        status="pending",
    )
    db.add(mpr)
    db.commit()
    db.refresh(mpr)

    # Send admin notification (non-blocking — don't fail if email fails)
    try:
        send_admin_payment_notification(
            full_name=mpr.full_name,
            email=mpr.email,
            phone=mpr.phone,
            amount=mpr.amount,
            created_at=mpr.created_at.strftime("%Y-%m-%d %H:%M") if mpr.created_at else "N/A",
        )
    except Exception as exc:
        logger.warning("Failed to send admin notification email: %s", exc)

    return {
        "id": mpr.id,
        "status": "pending",
        "message": "Request submitted successfully",
    }


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
    require_owner(current_user)  # 🔒 owner-only tab

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
    require_owner(current_user)  # 🔒 owner-only tab

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
    require_owner(current_user)  # 🔒 owner-only tab

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
    require_owner(current_user)  # 🔒 owner-only tab

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
        # Always extend from now (approval time), not from previous end_at
        user.end_at = now + timedelta(days=30)

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
    require_owner(current_user)  # 🔒 owner-only tab

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
    require_owner(current_user)  # 🔒 owner-only tab

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
