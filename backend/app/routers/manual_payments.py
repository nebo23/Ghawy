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
    full_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    amount: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
    receipt: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Submit a manual payment request with receipt screenshot."""
    # Validate email format (basic)
    email = email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(status_code=422, detail="Invalid email format")

    # Check if email already registered
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=409, detail="This email is already registered. Please login instead.")

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
        full_name=full_name.strip(),
        email=email,
        phone=phone.strip() if phone else None,
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
    require_admin(current_user)

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
    require_admin(current_user)

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
    require_admin(current_user)

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
    """Approve a payment request and send invite link."""
    require_admin(current_user)

    req = db.query(ManualPaymentRequest).filter(ManualPaymentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    # Generate invite token
    invite_token = secrets.token_urlsafe(32)
    now = datetime.utcnow()

    req.status = "approved"
    req.invite_token = invite_token
    req.invite_sent_at = now
    req.invite_expires_at = now + timedelta(hours=48)
    req.reviewed_by = current_user.id
    req.reviewed_at = now
    db.commit()

    # Build registration URL
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    registration_url = f"{frontend_url}/register.html?token={invite_token}"

    # Send approval email
    try:
        send_payment_approval_email(
            to_email=req.email,
            full_name=req.full_name,
            registration_url=registration_url,
        )
    except Exception as exc:
        logger.warning("Failed to send approval email to %s: %s", req.email, exc)

    return {
        "message": "approved",
        "invite_token": invite_token,
        "registration_url": registration_url,
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
    require_admin(current_user)

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
    """Resend invite with a new token (if expired or needs resending)."""
    require_admin(current_user)

    req = db.query(ManualPaymentRequest).filter(ManualPaymentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    if req.status != "approved":
        raise HTTPException(status_code=400, detail="Can only resend invites for approved requests")

    # Generate new token
    invite_token = secrets.token_urlsafe(32)
    now = datetime.utcnow()

    req.invite_token = invite_token
    req.invite_sent_at = now
    req.invite_expires_at = now + timedelta(hours=48)
    db.commit()

    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5500")
    registration_url = f"{frontend_url}/register.html?token={invite_token}"

    try:
        send_payment_approval_email(
            to_email=req.email,
            full_name=req.full_name,
            registration_url=registration_url,
        )
    except Exception as exc:
        logger.warning("Failed to resend invite email to %s: %s", req.email, exc)

    return {"message": "invite resent", "registration_url": registration_url}
