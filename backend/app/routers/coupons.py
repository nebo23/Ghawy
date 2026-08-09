"""
Coupons — the "what would this code do?" check behind the Apply button, and the
admin read-out of how close each code is to running out.

Nothing here charges anything or spends a slot. The authoritative decision is
taken again, under a row lock, at the moment a payment is actually created —
see app/services/coupon_service.py. This router exists so a member can be told
"that code is finished" before they reach the transfer screen instead of after.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Coupon, CouponRedemption, CouponRedemptionStatus, User
from app.routers.users import get_current_user
from app.services import coupon_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coupons", tags=["Coupons"])


class CouponPreviewIn(BaseModel):
    """What the browser is allowed to say about a coupon: its name.

    Note what is NOT here — no amount, no percentage, no discounted price. The
    plan key names a row in PLAN_PRICES and the server reads the money out of
    that. A `discount_percent` field on this model would be the 3500-vs-4000 bug
    all over again: a number the customer can edit deciding what they pay.
    """
    code: str
    plan_key: str


@router.post("/preview")
def preview(
    body: CouponPreviewIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Would this code work for me, and what would I pay?

    Answers 200 with `applied: false` and a reason for every kind of "no". A
    bad coupon is not a failed request — the page has to carry on offering the
    full price, and an error status would push the frontend into its generic
    "something went wrong" path.
    """
    # Imported here rather than at module scope: payment.py imports nothing from
    # this file, and keeping the arrow pointing one way avoids a circular import
    # if that ever changes.
    from app.routers.payment import PLAN_PRICES

    plan = PLAN_PRICES.get(body.plan_key)
    if not plan:
        raise HTTPException(status_code=400, detail="Invalid plan")

    result = coupon_service.preview_coupon(
        db,
        raw_code=body.code,
        user_id=current_user.id,
        amount=plan["amount"],
        currency=plan["currency"],
    )
    result["currency"] = plan["currency"]
    result["plan_key"] = body.plan_key
    # `original_amount` is filled in even on a refusal, so the page can put the
    # full price back on screen without a second request.
    if result.get("original_amount") is None:
        result["original_amount"] = float(plan["amount"])
    return result


def _require_admin(current_user: User):
    if not (getattr(current_user, "is_admin", False) or getattr(current_user, "is_owner", False)):
        raise HTTPException(status_code=403, detail="Admins only")


@router.get("/admin")
def admin_list(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Every coupon, how much of it is gone, and who took it.

    The client's actual question is "is the code about to run out", so `used`
    and `remaining` lead. `holds` is broken out separately because those are
    slots that are spoken for but not yet paid, and they can still evaporate —
    presenting them as used would have the panel report a coupon as finished
    that quietly refills half an hour later.
    """
    _require_admin(current_user)

    from datetime import datetime
    now = datetime.utcnow()

    out = []
    for coupon in db.query(Coupon).order_by(Coupon.id).all():
        rows = (
            db.query(CouponRedemption, User)
            .join(User, User.id == CouponRedemption.user_id)
            .filter(CouponRedemption.coupon_id == coupon.id)
            .order_by(CouponRedemption.created_at.desc())
            .all()
        )

        confirmed = 0
        holds = 0
        redemptions = []
        for r, u in rows:
            # A hold is only reclaimed (status -> expired) the next time someone
            # takes the coupon's lock, so a row can be PENDING here with its
            # deadline already behind it. Report what is true now rather than
            # what the column happens to say, or a quiet coupon shows holds that
            # lapsed days ago as if they might still be paid.
            live_hold = (
                r.status == CouponRedemptionStatus.PENDING.value
                and r.expires_at is not None
                and r.expires_at > now
            )
            if r.status == CouponRedemptionStatus.ACTIVE.value:
                confirmed += 1
            elif live_hold:
                holds += 1

            if r.status == CouponRedemptionStatus.PENDING.value and not live_hold:
                shown_status = CouponRedemptionStatus.EXPIRED.value
            else:
                shown_status = r.status

            redemptions.append({
                "id": r.id,
                "user_id": u.id,
                "user_name": u.full_name,
                "user_email": u.email,
                "status": shown_status,
                "slot_no": r.slot_no,
                "original_amount": float(r.original_amount) if r.original_amount is not None else None,
                "final_amount": float(r.final_amount) if r.final_amount is not None else None,
                "currency": r.currency,
                "plan_key": r.plan_key,
                "method": "instapay" if r.manual_request_id else "card",
                "payment_id": r.payment_id,
                "manual_request_id": r.manual_request_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "released_at": r.released_at.isoformat() if r.released_at else None,
            })

        used = confirmed + holds
        out.append({
            "id": coupon.id,
            "code": coupon.label,
            "discount_percent": float(coupon.discount_percent),
            "max_redemptions": coupon.max_redemptions,
            "used": used,
            "confirmed": confirmed,
            "holds": holds,
            "remaining": max(0, coupon.max_redemptions - used),
            "is_active": coupon.is_active,
            "redemptions": redemptions,
        })

    return {"coupons": out}
