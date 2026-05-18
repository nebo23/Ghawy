"""
Admin-only endpoints for manual operations like triggering recurring charges.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from passlib.context import CryptContext

from app.database import get_db
from app.models import User
from app.routers.users import get_current_user
from app.services.recurring import run_recurring_charges

router = APIRouter(prefix="/admin", tags=["Admin"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Helper ────────────────────────────────────────────────────
def require_admin(current_user: User):
    """Raise 403 if the current user is not an admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admins only")


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


# ── Existing: trigger recurring charges ───────────────────────
@router.post("/trigger-recurring")
async def trigger_recurring(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually trigger recurring charges. Admin only."""
    require_admin(current_user)
    results = await run_recurring_charges(db)
    return results


@router.post("/test-recurring/{user_id}")
async def test_recurring_for_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Test recurring charge for a specific user. Admin only."""
    require_admin(current_user)
    
    from app.services.recurring import charge_user
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.card_token:
        raise HTTPException(status_code=400, detail="User has no card token — has not paid via Kashier yet")
    
    success = await charge_user(user, db)
    return {
        "user_id": user_id,
        "email": user.email,
        "success": success,
        "card_token_exists": bool(user.card_token),
        "card_token_preview": user.card_token[:8] + "..." if user.card_token else None,
        "next_charge_at": str(user.next_charge_at),
        "subscription_end": str(user.subscription_end),
        "failed_charge_count": user.failed_charge_count,
    }

@router.get("/recurring-status")
async def get_recurring_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get overview of all recurring subscriptions. Admin only."""
    require_admin(current_user)
    
    from datetime import datetime
    now = datetime.utcnow()
    
    all_subscribers = db.query(User).filter(User.card_token.isnot(None), User.card_token != "").all()
    due_now = [u for u in all_subscribers if u.next_charge_at and u.next_charge_at <= now]
    upcoming = [u for u in all_subscribers if u.next_charge_at and u.next_charge_at > now]
    
    return {
        "total_subscribers": len(all_subscribers),
        "due_now": len(due_now),
        "upcoming_7_days": len([u for u in upcoming if (u.next_charge_at - now).days <= 7]),
        "subscribers": [
            {
                "user_id": u.id,
                "email": u.email,
                "full_name": u.full_name,
                "subscription_type": u.subscription_type,
                "last_charged_at": str(u.last_charged_at),
                "next_charge_at": str(u.next_charge_at),
                "subscription_end": str(u.subscription_end),
                "is_active": u.is_active,
                "failed_charge_count": u.failed_charge_count or 0,
                "days_until_charge": (u.next_charge_at - now).days if u.next_charge_at and u.next_charge_at > now else ( -1 if u.next_charge_at and u.next_charge_at < now else None),
            }
            for u in all_subscribers
        ]
    }


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
    """Return list of all users with admin-relevant fields."""
    require_admin(current_user)

    query = db.query(User)

    # Search filter
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.full_name.ilike(search_term)) | (User.email.ilike(search_term))
        )

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
            "email": u.email,
            "phone": u.phone,
            "country": u.country,
            "is_active": u.is_active,
            "is_verified": u.is_verified,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
            "badge": u.badge,
            "avatar_url": u.avatar_url,
            "subscription_type": u.subscription_type,
            "subscription_start": u.subscription_start.isoformat() if u.subscription_start else None,
            "subscription_end": u.subscription_end.isoformat() if u.subscription_end else None,
            "next_charge_at": u.next_charge_at.isoformat() if u.next_charge_at else None,
            "last_charged_at": u.last_charged_at.isoformat() if u.last_charged_at else None,
            "has_card_token": bool(u.card_token),
            "failed_charge_count": u.failed_charge_count or 0,
            "days_until_charge": (u.next_charge_at - now).days if u.next_charge_at and u.next_charge_at > now else ( -1 if u.next_charge_at and u.next_charge_at < now else None),
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
def toggle_active(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Toggle a user's is_active status."""
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = not user.is_active
    db.commit()

    return {
        "user_id": user.id,
        "is_active": user.is_active,
        "message": f"User {'activated' if user.is_active else 'deactivated'} successfully",
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


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a user and all related data (cascade via model relationships)."""
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent admin from deleting themselves
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account from admin panel")

    db.delete(user)
    db.commit()

    return {"message": f"User '{user.full_name}' deleted successfully"}


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
