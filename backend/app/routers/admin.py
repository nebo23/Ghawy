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
from app.models import (
    User, Payment, PaymentStatus, PaymentMethod, AdminMemberNote,
    Course, Lesson, UserProgress, UserCourseProgress, Certificate, Exam, ExamAttempt,
)
from app.routers.users import get_current_user
from app.services.name_utils import split_full_name


router = APIRouter(prefix="/admin", tags=["Admin"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Helper ────────────────────────────────────────────────────
def require_admin(current_user: User):
    """Raise 403 if the current user is neither an admin nor an owner."""
    if not (getattr(current_user, 'is_admin', False) or getattr(current_user, 'is_owner', False)):
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

    # ── Batch-load confirmed payments (paid status + package) in one query ──
    # A member "actually paid" iff they have a CONFIRMED payment (covers both
    # Kashier and approved manual payments, which both write a CONFIRMED row).
    # We keep the latest confirmed plan_key as the member's current package.
    paid_map = {}  # user_id -> latest plan_key (or None)
    user_ids = [u.id for u in users]
    if user_ids:
        pay_rows = (
            db.query(Payment.user_id, Payment.plan_key, Payment.confirmed_at, Payment.created_at)
            .filter(Payment.user_id.in_(user_ids), Payment.status == PaymentStatus.CONFIRMED)
            .all()
        )
        # Pick the most recent confirmed payment per user (by confirmed_at, then created_at)
        best_ts = {}
        for uid, plan_key, confirmed_at, created_at in pay_rows:
            ts = confirmed_at or created_at or datetime.min
            if uid not in best_ts or ts >= best_ts[uid]:
                best_ts[uid] = ts
                paid_map[uid] = plan_key

    result = []
    for u in users:
        result.append({
            "id": u.id,
            "full_name": u.full_name,
            # Contact details are owner-only — redacted for non-owner admins
            "email": u.email if viewer_is_owner else None,
            "phone": u.phone if viewer_is_owner else None,
            "country": u.country,
            "birth_date": u.birth_date.isoformat() if u.birth_date else None,
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
            "winback_sent_at": u.winback_email_sent_at.isoformat() if u.winback_email_sent_at else None,
            # Subscription/package fields for Team Dashboard filtering & sorting
            "has_paid": u.id in paid_map,
            "plan_key": paid_map.get(u.id),
            "subscription_source": u.subscription_source,
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

    admin_first, admin_last = split_full_name(data.full_name)
    new_user = User(
        full_name=data.full_name,
        first_name=admin_first,
        last_name=admin_last,
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
    require_admin(current_user)  # 🔒 admins + owners

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
    require_admin(current_user)  # 🔒 admins + owners

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
    require_admin(current_user)  # 🔒 admins + owners

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
    require_admin(current_user)  # 🔒 admins + owners

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
    require_admin(current_user)  # 🔒 admins + owners

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
    require_admin(current_user)  # 🔒 admins + owners

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
    require_admin(current_user)  # 🔒 admins + owners

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
    require_admin(current_user)  # 🔒 admins + owners

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


@router.get("/analytics/subscription-breakdown")
def subscription_breakdown(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Distribution of current subscription types across members (monthly / yearly / none)."""
    require_admin(current_user)  # 🔒 admins + owners

    from app.models import ManualPaymentRequest

    now = datetime.utcnow()

    # Latest confirmed payment plan per user (kashier + backfilled manual payments).
    # Ordered ascending so the last write wins = the most recent plan.
    plan_by_user = {}
    for pay in db.query(Payment).filter(
        Payment.status == PaymentStatus.CONFIRMED
    ).order_by(Payment.created_at.asc()).all():
        if pay.plan_key:
            plan_by_user[pay.user_id] = pay.plan_key

    # Fallback: plan chosen on approved manual payment requests (keyed by email).
    plan_by_email = {}
    for req in db.query(ManualPaymentRequest).filter(
        ManualPaymentRequest.status == "approved"
    ).order_by(ManualPaymentRequest.created_at.asc()).all():
        if req.plan:
            plan_by_email[req.email] = req.plan

    monthly = quarterly = yearly = none = 0
    for u in db.query(User).all():
        # A member counts as subscribed only while their access is still active.
        active = bool(u.is_active) and (u.end_at is None or u.end_at > now)
        if not active:
            none += 1
            continue
        plan = (plan_by_user.get(u.id) or plan_by_email.get(u.email) or "").lower()
        if "year" in plan:
            yearly += 1
        elif "quarter" in plan:
            quarterly += 1
        else:
            monthly += 1

    return {"monthly": monthly, "quarterly": quarterly, "yearly": yearly, "none": none}


# ══════════════════════════════════════════════════════════════
#  STUDENTS PROGRESS ENDPOINTS
# ══════════════════════════════════════════════════════════════

def _effective_lesson_totals(db: Session, courses):
    """Effective lesson count per course — mirrors the student-facing rule in
    courses.get_course_progress: count only 'ready' lessons, fall back to all
    lessons when the course has none ready."""
    all_counts = dict(
        db.query(Lesson.course_id, sql_func.count(Lesson.id))
        .group_by(Lesson.course_id).all()
    )
    ready_counts = dict(
        db.query(Lesson.course_id, sql_func.count(Lesson.id))
        .filter(Lesson.video_status == "ready")
        .group_by(Lesson.course_id).all()
    )
    totals = {c.id: (ready_counts.get(c.id) or all_counts.get(c.id, 0)) for c in courses}
    return totals, ready_counts


@router.get("/students-progress")
def students_progress(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Course progress for every member across all courses (admins + owners).

    Aggregate queries only (no N+1): grouped completed-lesson counts, exam
    bests and certificates are each fetched once and joined in Python.
    """
    require_admin(current_user)

    courses = db.query(Course).order_by(Course.sort_order.asc(), Course.id.asc()).all()
    course_total, ready_counts = _effective_lesson_totals(db, courses)

    # Completed lessons per (user, course) — same ready/fallback rule as totals
    ready_done = {}
    for uid, cid, cnt in (
        db.query(UserProgress.user_id, UserProgress.course_id, sql_func.count(UserProgress.id))
        .join(Lesson, Lesson.id == UserProgress.lesson_id)
        .filter(Lesson.video_status == "ready")
        .group_by(UserProgress.user_id, UserProgress.course_id).all()
    ):
        ready_done[(uid, cid)] = cnt

    all_done = {}
    last_completed = {}
    for uid, cid, cnt, last in (
        db.query(
            UserProgress.user_id, UserProgress.course_id,
            sql_func.count(UserProgress.id), sql_func.max(UserProgress.completed_at),
        )
        .group_by(UserProgress.user_id, UserProgress.course_id).all()
    ):
        all_done[(uid, cid)] = cnt
        last_completed[(uid, cid)] = last

    # Last time the student opened each course (set even before completing anything)
    last_access = {
        (uid, cid): accessed
        for uid, cid, accessed in db.query(
            UserCourseProgress.user_id, UserCourseProgress.course_id, UserCourseProgress.last_accessed
        ).all()
    }

    cert_pairs = {
        (uid, cid) for uid, cid in db.query(Certificate.user_id, Certificate.course_id).all()
    }

    exam_counts = dict(
        db.query(Exam.course_id, sql_func.count(Exam.id))
        .filter(Exam.is_published == True)
        .group_by(Exam.course_id).all()
    )
    best_score = {
        (uid, cid): best
        for uid, cid, best in db.query(
            ExamAttempt.user_id, ExamAttempt.course_id, sql_func.max(ExamAttempt.score)
        ).group_by(ExamAttempt.user_id, ExamAttempt.course_id).all()
    }
    exams_passed = {
        (uid, cid): cnt
        for uid, cid, cnt in db.query(
            ExamAttempt.user_id, ExamAttempt.course_id,
            sql_func.count(sql_func.distinct(ExamAttempt.exam_id)),
        ).filter(ExamAttempt.passed == True)
        .group_by(ExamAttempt.user_id, ExamAttempt.course_id).all()
    }

    # Group every touched course per user (progress, course opened, or exam attempt)
    touched_by_user = {}
    for uid, cid in set(all_done) | set(last_access) | set(best_score):
        touched_by_user.setdefault(uid, set()).add(cid)

    course_by_id = {c.id: c for c in courses}
    course_order = {c.id: i for i, c in enumerate(courses)}
    # Overall denominator = published courses that actually have lessons
    published_ids = [c.id for c in courses if c.is_published and course_total.get(c.id, 0) > 0]
    overall_total = sum(course_total[cid] for cid in published_ids)

    def done_for(uid, cid):
        """Completed count for a (user, course) honoring the ready/fallback rule, capped at the course total."""
        if ready_counts.get(cid, 0) > 0:
            done = ready_done.get((uid, cid), 0)
        else:
            done = all_done.get((uid, cid), 0)
        return min(done, course_total.get(cid, 0))

    users = db.query(User).order_by(User.created_at.desc()).all()
    students = []
    for u in users:
        touched = touched_by_user.get(u.id, set())
        course_entries = []
        courses_completed = 0
        user_last_activity = None

        for cid in sorted(touched, key=lambda c: course_order.get(c, 10**9)):
            course = course_by_id.get(cid)
            if not course:
                continue  # progress rows pointing at a deleted course
            total = course_total.get(cid, 0)
            done = done_for(u.id, cid)
            percent = round(done / total * 100) if total > 0 else 0
            if percent >= 100 and total > 0:
                courses_completed += 1

            lc = last_completed.get((u.id, cid))
            la = last_access.get((u.id, cid))
            activity = max([d for d in (lc, la) if d is not None], default=None)
            if activity and (user_last_activity is None or activity > user_last_activity):
                user_last_activity = activity

            course_entries.append({
                "course_id": cid,
                "title": course.title,
                "is_published": bool(course.is_published),
                "completed_lessons": done,
                "total_lessons": total,
                "percent": percent,
                "last_activity": activity.isoformat() if activity else None,
                "exams_total": exam_counts.get(cid, 0),
                "exams_passed": exams_passed.get((u.id, cid), 0),
                "best_exam_score": best_score.get((u.id, cid)),
                "has_certificate": (u.id, cid) in cert_pairs,
            })

        overall_done = sum(done_for(u.id, cid) for cid in published_ids)
        students.append({
            "id": u.id,
            "full_name": u.full_name,
            "avatar_url": u.avatar_url,
            "is_active": bool(u.is_active),
            "is_admin": bool(u.is_admin),
            "is_owner": bool(getattr(u, "is_owner", False)),
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
            "overall_completed": overall_done,
            "overall_total": overall_total,
            "overall_percent": round(overall_done / overall_total * 100) if overall_total > 0 else 0,
            "courses_started": len(course_entries),
            "courses_completed": courses_completed,
            "certificates": sum(1 for (uid, _cid) in cert_pairs if uid == u.id),
            "exams_passed": sum(cnt for (uid, _cid), cnt in exams_passed.items() if uid == u.id),
            "last_activity": user_last_activity.isoformat() if user_last_activity else None,
            "courses": course_entries,
        })

    return {
        "overall_total_lessons": overall_total,
        "courses": [
            {
                "id": c.id,
                "title": c.title,
                "is_published": bool(c.is_published),
                "total_lessons": course_total.get(c.id, 0),
                "exams_total": exam_counts.get(c.id, 0),
            }
            for c in courses
        ],
        "students": students,
    }


@router.get("/students-progress/{user_id}/courses/{course_id}/lessons")
def student_course_lessons(
    user_id: int,
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lesson-by-lesson completion for one student in one course (admins + owners)."""
    require_admin(current_user)

    student = db.query(User).filter(User.id == user_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="User not found")
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    lessons = (
        db.query(Lesson)
        .filter(Lesson.course_id == course_id)
        .order_by(Lesson.order.asc(), Lesson.id.asc())
        .all()
    )
    completed_at = {
        r.lesson_id: r.completed_at
        for r in db.query(UserProgress).filter(
            UserProgress.user_id == user_id,
            UserProgress.course_id == course_id,
        ).all()
    }

    return {
        "student": {"id": student.id, "full_name": student.full_name, "avatar_url": student.avatar_url},
        "course": {"id": course.id, "title": course.title},
        "lessons": [
            {
                "id": l.id,
                "title": l.title,
                "section_title": l.section_title,
                "duration_minutes": l.duration_minutes or 0,
                "video_status": l.video_status,
                "completed": l.id in completed_at,
                "completed_at": completed_at[l.id].isoformat() if l.id in completed_at else None,
            }
            for l in lessons
        ],
    }


