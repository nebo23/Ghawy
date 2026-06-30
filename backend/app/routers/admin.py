"""
Admin-only endpoints for manual operations like triggering recurring charges.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.sql import func as sql_func
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from passlib.context import CryptContext
from starlette.responses import StreamingResponse
from datetime import datetime, timedelta
import csv
import io

from app.database import get_db
from app.models import User, Payment, PaymentStatus, PaymentMethod, AdminMemberNote
from app.routers.users import get_current_user


router = APIRouter(prefix="/admin", tags=["Admin"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Helper ────────────────────────────────────────────────────
def require_admin(current_user: User):
    """Raise 403 if the current user is not an admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")


def require_owner(current_user: User):
    """Raise 403 if the current user is not an owner."""
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")


# ── Schemas ───────────────────────────────────────────────────
class AdminAddUser(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    country: Optional[str] = None
    is_active: bool = True
    is_admin: bool = False


class AdminResetPassword(BaseModel):
    new_password: str


class AdminMemberNoteIn(BaseModel):
    note: str = ""



# ══════════════════════════════════════════════════════════════
#  USER MANAGEMENT ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.get("/users")
def list_users(
    search: Optional[str] = Query(None),
    status: str = Query("all"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return list of all users with admin-relevant fields.

    Admins may view the members list, but contact details (email, phone,
    social link) are redacted for non-owner admins — only owners see them.
    """
    require_admin(current_user)
    viewer_is_owner = bool(getattr(current_user, "is_owner", False))

    query = db.query(User)

    # Search filter — non-owner admins cannot search by email (it's hidden),
    # so restrict their search to full_name only to avoid email enumeration.
    if search:
        search_term = f"%{search}%"
        if viewer_is_owner:
            query = query.filter(
                (User.full_name.ilike(search_term)) | (User.email.ilike(search_term))
            )
        else:
            query = query.filter(User.full_name.ilike(search_term))

    # Status filter
    if status == "active":
        query = query.filter(User.is_active == True)
    elif status == "inactive":
        query = query.filter(User.is_active == False)

    users = query.order_by(User.created_at.desc()).all()

    # Build response list (return ALL matching users — client does pagination)
    from datetime import datetime
    now = datetime.utcnow()
    
    result = []
    for u in users:
        result.append({
            "id": u.id,
            "full_name": u.full_name,
            # Contact details are owner-only — redacted for non-owner admins
            "email": u.email if viewer_is_owner else None,
            "phone": u.phone if viewer_is_owner else None,
            "country": u.country,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
            "badge": u.badge,
            "custom_title": u.custom_title or "",
            "avatar_url": u.avatar_url,
            "end_at": u.end_at.isoformat() if u.end_at else None,
            "governorate": u.governorate,
            "social_media_url": u.social_media_url if viewer_is_owner else None,
            "is_owner": getattr(u, 'is_owner', False),
        })

    return result


@router.post("/users/add")
def add_user(
    data: AdminAddUser,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new user (admin-created users are auto-verified)."""
    require_admin(current_user)

    # Check for duplicate email
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")

    # Check for duplicate phone (if provided)
    if data.phone:
        existing_phone = db.query(User).filter(User.phone == data.phone).first()
        if existing_phone:
            raise HTTPException(status_code=400, detail="Phone number already exists")

    new_user = User(
        full_name=data.full_name,
        email=data.email,
        hashed_password=pwd_context.hash(data.password),
        phone=data.phone,
        country=data.country,
        is_active=data.is_active,
        is_admin=data.is_admin,
        is_verified=True,  # Admin-created users are auto-verified
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "id": new_user.id,
        "full_name": new_user.full_name,
        "email": new_user.email,
        "is_active": new_user.is_active,
        "is_admin": new_user.is_admin,
        "message": "User created successfully",
    }


@router.patch("/users/{user_id}/toggle-active")
async def toggle_active(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle a user's is_active status. When activating, sets end_at = now + 30 days if not already set."""
    from app.services.ws_manager import manager as ws_manager
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active

    # When activating, set end_at to 30 days from now if not already set or already expired
    if user.is_active:
        now = datetime.utcnow()
        if not user.end_at or user.end_at <= now:
            user.end_at = now + timedelta(days=30)
    else:
        # When deactivating, clear end_at and disconnect from WS
        user.end_at = None

    db.commit()

    # Force-disconnect user from WebSocket if deactivated
    if not user.is_active:
        await ws_manager.disconnect_user(user_id)

    return {
        "user_id": user.id,
        "is_active": user.is_active,
        "end_at": user.end_at.isoformat() if user.end_at else None,
        "message": f"User {'activated' if user.is_active else 'deactivated'} successfully",
    }


class SetSubscriptionRequest(BaseModel):
    days: int = 30  # عدد الأيام من دلوقتي


@router.patch("/users/{user_id}/set-subscription")
def set_subscription(
    user_id: int,
    data: SetSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set subscription end_at to now + N days and activate the user."""
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.utcnow()
    user.is_active = True
    user.end_at = now + timedelta(days=data.days)
    db.commit()

    return {
        "user_id": user.id,
        "is_active": True,
        "end_at": user.end_at.isoformat(),
        "message": f"Subscription set for {data.days} days (expires {user.end_at.strftime('%Y-%m-%d')})",
    }


@router.patch("/users/{user_id}/toggle-admin")
def toggle_admin(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle a user's is_admin status."""
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_admin = not user.is_admin
    db.commit()

    return {
        "user_id": user.id,
        "is_admin": user.is_admin,
        "message": f"User {'promoted to admin' if user.is_admin else 'removed from admin'} successfully",
    }


@router.patch("/users/{user_id}/toggle-owner")
def toggle_owner(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle a user's is_owner status. Only owners can do this."""
    # 🔒 Only owners can promote/demote owners
    if not getattr(current_user, 'is_owner', False):
        raise HTTPException(status_code=403, detail="Owners only")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_owner = not user.is_owner
    # Owners must also be admins
    if user.is_owner:
        user.is_admin = True
    db.commit()

    return {
        "user_id": user.id,
        "is_owner": user.is_owner,
        "is_admin": user.is_admin,
        "message": f"User {'promoted to owner' if user.is_owner else 'removed from owner'} successfully",
    }


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user and all related data (cascade via model relationships)."""
    from app.services.ws_manager import manager as ws_manager
    require_owner(current_user)  # 🔒 owner-only — admins cannot delete members

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account from admin panel")

    # Force-disconnect user from WebSocket BEFORE deleting from DB
    await ws_manager.disconnect_user(user_id)

    # Clean up related records that lack ON DELETE CASCADE
    from app.models import PhoneOTP, UserProgress, Certificate, Channel, LiveSession, ManualPaymentRequest

    db.query(PhoneOTP).filter(PhoneOTP.user_id == user.id).delete(synchronize_session=False)
    db.query(UserProgress).filter(UserProgress.user_id == user.id).delete(synchronize_session=False)
    db.query(Certificate).filter(Certificate.user_id == user.id).delete(synchronize_session=False)

    db.query(Channel).filter(Channel.created_by == user.id).update({"created_by": None}, synchronize_session=False)
    db.query(LiveSession).filter(LiveSession.instructor_id == user.id).update({"instructor_id": None}, synchronize_session=False)
    db.query(LiveSession).filter(LiveSession.created_by == user.id).update({"created_by": None}, synchronize_session=False)
    db.query(ManualPaymentRequest).filter(ManualPaymentRequest.reviewed_by == user.id).update({"reviewed_by": None}, synchronize_session=False)

    saved_name = user.full_name
    db.delete(user)
    db.commit()

    return {"message": f"User '{saved_name}' deleted successfully"}


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    data: AdminResetPassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reset a user's password (admin only)."""
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = pwd_context.hash(data.new_password)
    db.commit()

    return {"message": f"Password reset successfully for {user.full_name}"}


# ══════════════════════════════════════════════════════════════
#  ADMIN MEMBER NOTES (private, admin-only)
# ══════════════════════════════════════════════════════════════

@router.get("/notes/{user_id}")
def get_member_note(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the private admin note for a member (admin only)."""
    require_admin(current_user)

    member = db.query(User).filter(User.id == user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="User not found")

    record = db.query(AdminMemberNote).filter(AdminMemberNote.member_id == user_id).first()
    return {"user_id": user_id, "note": record.note if record else ""}


@router.post("/notes/{user_id}")
def save_member_note(
    user_id: int,
    data: AdminMemberNoteIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create or update the private admin note for a member (admin only)."""
    require_admin(current_user)

    member = db.query(User).filter(User.id == user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="User not found")

    note_text = (data.note or "").strip()

    record = db.query(AdminMemberNote).filter(AdminMemberNote.member_id == user_id).first()
    if record:
        record.note = note_text
        record.updated_by = current_user.id
    else:
        record = AdminMemberNote(member_id=user_id, note=note_text, updated_by=current_user.id)
        db.add(record)

    db.commit()
    db.refresh(record)
    return {"user_id": user_id, "note": record.note, "message": "Note saved"}


# ══════════════════════════════════════════════════════════════
#  PAYMENTS ENDPOINTS
# ══════════════════════════════════════════════════════════════

def _map_status_to_display(status_val):
    """Map DB payment status to display string."""
    mapping = {
        "confirmed": "paid",
        "rejected": "failed",
        "pending": "pending",
        "refunded": "refunded",
    }
    s = status_val.value if hasattr(status_val, 'value') else str(status_val)
    return mapping.get(s, s)


def _map_filter_to_db(status_filter):
    """Map display status filter to DB enum value."""
    mapping = {
        "paid": "confirmed",
        "failed": "rejected",
        "pending": "pending",
        "refunded": "refunded",
    }
    return mapping.get(status_filter, None)


@router.get("/payments")
def list_payments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List payments with pagination, search and filters."""
    require_owner(current_user)  # 🔒 owner-only tab

    query = db.query(Payment, User).outerjoin(User, Payment.user_id == User.id)

    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(search_term)) |
            (Payment.provider_order_id.ilike(search_term))
        )

    # Status filter
    if status and status != "all":
        db_status = _map_filter_to_db(status)
        if db_status:
            query = query.filter(Payment.status == db_status)

    # Method filter
    if method and method != "all":
        query = query.filter(Payment.method == method)

    # Count total
    total = query.count()
    pages = max(1, (total + limit - 1) // limit)

    # Paginate
    payments = query.order_by(Payment.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    result = []
    for payment, user in payments:
        result.append({
            "id": payment.id,
            "member_name": user.full_name if user else "Unknown",
            "member_avatar": user.avatar_url if user else None,
            "email": user.email if user else "",
            "date": payment.created_at.isoformat() if payment.created_at else None,
            "amount": float(payment.amount) if payment.amount else 0,
            "currency": payment.currency or "EGP",
            "method": payment.method.value if payment.method else "",
            "status": _map_status_to_display(payment.status),
            "reference": payment.provider_order_id or str(payment.id),
        })

    return {"payments": result, "total": total, "page": page, "pages": pages}


@router.get("/payments/stats")
def payment_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate payment statistics."""
    require_owner(current_user)  # 🔒 owner-only tab

    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_revenue = db.query(sql_func.coalesce(sql_func.sum(Payment.amount), 0)).filter(
        Payment.status == PaymentStatus.CONFIRMED
    ).scalar()

    this_month = db.query(sql_func.coalesce(sql_func.sum(Payment.amount), 0)).filter(
        Payment.status == PaymentStatus.CONFIRMED,
        Payment.created_at >= month_start
    ).scalar()

    failed_count = db.query(sql_func.count(Payment.id)).filter(
        Payment.status == PaymentStatus.REJECTED
    ).scalar()

    pending_count = db.query(sql_func.count(Payment.id)).filter(
        Payment.status == PaymentStatus.PENDING
    ).scalar()

    return {
        "total_revenue": float(total_revenue),
        "this_month": float(this_month),
        "failed_count": failed_count,
        "pending_count": pending_count,
    }


@router.get("/payments/export-csv")
def export_payments_csv(
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export filtered payments as CSV."""
    require_owner(current_user)  # 🔒 owner-only tab

    query = db.query(Payment, User).outerjoin(User, Payment.user_id == User.id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(search_term)) |
            (Payment.provider_order_id.ilike(search_term))
        )

    if status and status != "all":
        db_status = _map_filter_to_db(status)
        if db_status:
            query = query.filter(Payment.status == db_status)

    if method and method != "all":
        query = query.filter(Payment.method == method)

    payments = query.order_by(Payment.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Member Name", "Email", "Date", "Amount", "Currency", "Method", "Status", "Reference"])

    for payment, user in payments:
        writer.writerow([
            payment.id,
            user.full_name if user else "Unknown",
            user.email if user else "",
            payment.created_at.isoformat() if payment.created_at else "",
            float(payment.amount) if payment.amount else 0,
            payment.currency or "EGP",
            payment.method.value if payment.method else "",
            _map_status_to_display(payment.status),
            payment.provider_order_id or str(payment.id),
        ])

    output.seek(0)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=ghawy_payments_{today}.csv"},
    )


@router.post("/payments/{payment_id}/retry")
def retry_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retry a failed payment."""
    require_owner(current_user)  # 🔒 owner-only tab

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != PaymentStatus.REJECTED:
        raise HTTPException(status_code=400, detail="Only failed payments can be retried")

    payment.status = PaymentStatus.PENDING
    db.commit()
    return {"message": "retried"}


@router.post("/payments/{payment_id}/refund")
def refund_payment(
    payment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a paid payment as refunded."""
    require_owner(current_user)  # 🔒 owner-only tab

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status != PaymentStatus.CONFIRMED:
        raise HTTPException(status_code=400, detail="Only paid payments can be refunded")

    payment.status = PaymentStatus.REFUNDED
    db.commit()
    return {"message": "refunded"}


# ══════════════════════════════════════════════════════════════
#  ANALYTICS ENDPOINTS
# ══════════════════════════════════════════════════════════════

def _parse_range(range_str: str) -> datetime:
    """Parse range string to a start datetime."""
    now = datetime.utcnow()
    mapping = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "6mo": timedelta(days=180),
        "1yr": timedelta(days=365),
    }
    delta = mapping.get(range_str, timedelta(days=30))
    return now - delta


@router.get("/analytics/kpis")
def analytics_kpis(
    range: str = Query("30d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """KPI metrics for the analytics dashboard."""
    require_owner(current_user)  # 🔒 owner-only tab

    now = datetime.utcnow()
    start = _parse_range(range)
    period_length = now - start
    prev_start = start - period_length

    total_members = db.query(sql_func.count(User.id)).scalar()

    new_this_period = db.query(sql_func.count(User.id)).filter(
        User.created_at >= start
    ).scalar()

    new_prev_period = db.query(sql_func.count(User.id)).filter(
        User.created_at >= prev_start,
        User.created_at < start
    ).scalar()

    growth_rate = 0.0
    if new_prev_period > 0:
        growth_rate = ((new_this_period - new_prev_period) / new_prev_period) * 100
    elif new_this_period > 0:
        growth_rate = 100.0

    total_revenue = float(db.query(
        sql_func.coalesce(sql_func.sum(Payment.amount), 0)
    ).filter(Payment.status == PaymentStatus.CONFIRMED).scalar())

    # Churn: users deactivated (is_active=False) as % of total
    inactive_count = db.query(sql_func.count(User.id)).filter(
        User.is_active == False
    ).scalar()
    churn_rate = (inactive_count / total_members * 100) if total_members > 0 else 0.0

    return {
        "total_members": total_members,
        "growth_rate": round(growth_rate, 1),
        "total_revenue": total_revenue,
        "churn_rate": round(churn_rate, 1),
    }


@router.get("/analytics/members-over-time")
def members_over_time(
    range: str = Query("30d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Daily new member signups for the given range."""
    require_owner(current_user)  # 🔒 owner-only tab

    start = _parse_range(range)
    now = datetime.utcnow()

    users = db.query(User).filter(User.created_at >= start).all()

    # Group by date
    counts = {}
    d = start.date()
    while d <= now.date():
        counts[d.isoformat()] = 0
        d += timedelta(days=1)

    for u in users:
        if u.created_at:
            day = u.created_at.date().isoformat()
            if day in counts:
                counts[day] += 1

    return [{"date": date, "count": count} for date, count in sorted(counts.items())]


@router.get("/analytics/revenue-over-time")
def revenue_over_time(
    range: str = Query("30d"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Daily revenue from confirmed payments for the given range."""
    require_owner(current_user)  # 🔒 owner-only tab

    start = _parse_range(range)
    now = datetime.utcnow()

    payments = db.query(Payment).filter(
        Payment.status == PaymentStatus.CONFIRMED,
        Payment.created_at >= start
    ).all()

    # Group by date
    amounts = {}
    d = start.date()
    while d <= now.date():
        amounts[d.isoformat()] = 0.0
        d += timedelta(days=1)

    for p in payments:
        if p.created_at:
            day = p.created_at.date().isoformat()
            if day in amounts:
                amounts[day] += float(p.amount) if p.amount else 0

    return [{"date": date, "amount": round(amt, 2)} for date, amt in sorted(amounts.items())]


