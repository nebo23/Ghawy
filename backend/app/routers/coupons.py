"""
Coupons — the "what would this code do?" check behind the Apply button, and the
admin read-out of how close each code is to running out.

Nothing here charges anything or spends a slot. The authoritative decision is
taken again, under a row lock, at the moment a payment is actually created —
see app/services/coupon_service.py. This router exists so a member can be told
"that code is finished" before they reach the transfer screen instead of after.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Coupon, CouponRedemption, CouponRedemptionStatus, User
from app.routers.users import get_current_user
from app.schemas import CouponCreate, CouponUpdate
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


def _require_owner(current_user: User):
    """Reading the panel is an admin job; changing what a coupon costs is not.

    Same shape of refusal as admin.py and guests.py so the dashboard's existing
    403 handling covers this too. Hiding the buttons in the frontend is
    cosmetics — this is the gate.
    """
    if not getattr(current_user, "is_owner", False):
        raise HTTPException(status_code=403, detail="Owners only")


def _coupon_card(db: Session, coupon: Coupon, now: Optional[datetime] = None) -> dict:
    """One coupon, in the exact shape the panel renders.

    Shared by the list, the create and the update so a card refreshed after a
    save is the same object the page started with — the alternative is the
    frontend reconstructing a card from a partial response and slowly drifting
    away from what a reload would show.
    """
    now = now or datetime.utcnow()

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
    return {
        "id": coupon.id,
        "code": coupon.label,
        # The lookup key, lowercase, as it is actually matched. The edit form
        # quotes it under the display-spelling field so it is obvious which of
        # the two is the thing people type.
        "lookup_code": coupon.code,
        "discount_percent": float(coupon.discount_percent),
        "max_redemptions": coupon.max_redemptions,
        "used": used,
        "confirmed": confirmed,
        "holds": holds,
        # max(0, ...) and not the raw subtraction: the cap can be lowered below
        # what has already been taken, and "-4 left" is not a thing.
        "remaining": max(0, coupon.max_redemptions - used),
        "is_active": coupon.is_active,
        "redemptions": redemptions,
    }


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

    now = datetime.utcnow()
    coupons = db.query(Coupon).order_by(Coupon.id).all()
    return {"coupons": [_coupon_card(db, c, now) for c in coupons]}


@router.post("/admin", status_code=201)
def admin_create(
    body: CouponCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mint a new code. Owners only.

    The typed text is kept twice, on purpose: `code` lowercased is what a
    member's input is matched against, `display_code` is what everyone reads.
    """
    _require_owner(current_user)

    code = coupon_service.normalize_code(body.code)
    if not code:
        raise HTTPException(status_code=422, detail="Code cannot be empty")

    # Checked here so the answer is a clear 409 rather than a 500 out of the
    # unique index — and caught below as well, because these two race: another
    # owner can insert the same code between this SELECT and our INSERT.
    if db.query(Coupon).filter(Coupon.code == code).first():
        raise HTTPException(status_code=409, detail=f"A coupon with the code “{body.code}” already exists")

    coupon = Coupon(
        code=code,
        display_code=body.code,
        discount_percent=body.discount_percent,
        max_redemptions=body.max_redemptions,
        is_active=body.is_active,
    )
    db.add(coupon)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"A coupon with the code “{body.code}” already exists")
    db.refresh(coupon)

    logger.info("🎟️ Coupon %s created by owner %s (%s%% off, max %s, active=%s)",
                coupon.code, current_user.id, coupon.discount_percent,
                coupon.max_redemptions, coupon.is_active)
    return _coupon_card(db, coupon)


@router.patch("/admin/{coupon_id}")
def admin_update(
    coupon_id: int,
    body: CouponUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change a coupon's terms. Owners only. `code` is not changeable.

    Three things this deliberately does NOT do:

      - It does not touch `code`. See the note on CouponUpdate in schemas.py.
      - It does not rewrite past redemptions. `original_amount` and
        `final_amount` were recorded at the moment of use so a dispute is
        settled by what was actually charged; a percentage change applies to
        new redemptions only.
      - It does not cancel live holds when the percentage changes. A member who
        is already on the Kashier page holds a signed order for the price they
        were quoted, and that order stays payable for its half hour. Voiding it
        would move the number under someone mid-payment — worse than a handful
        of transfers settling at yesterday's discount. (If they come back and
        start a *new* checkout, reserve_redemption reprices their existing hold
        at the current percentage, which is what a new quote should do.)

    Lowering `max_redemptions` below what has already been taken is allowed and
    releases nobody: the people below the new cap keep their slots, `remaining`
    floors at zero, and the next member to try the code is refused with
    `exhausted` by the usual count-under-lock in coupon_service.
    """
    _require_owner(current_user)

    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return _coupon_card(db, coupon)

    if "display_code" in fields and fields["display_code"] is not None:
        display = fields["display_code"]
        # Capitalisation only. A display name that spells a different word from
        # the code would put a code on screen and on the receipt that does not
        # work when anybody types it.
        if coupon_service.normalize_code(display) != coupon.code:
            raise HTTPException(
                status_code=422,
                detail=f"The display name can only change capitalisation of “{coupon.code}” — "
                       "the code itself cannot be renamed",
            )
        coupon.display_code = display

    if fields.get("discount_percent") is not None:
        coupon.discount_percent = fields["discount_percent"]
    if fields.get("max_redemptions") is not None:
        coupon.max_redemptions = fields["max_redemptions"]
    if fields.get("is_active") is not None:
        coupon.is_active = fields["is_active"]

    db.commit()
    db.refresh(coupon)

    logger.info("🎟️ Coupon %s updated by owner %s (%s)", coupon.code, current_user.id,
                ", ".join(f"{k}={v}" for k, v in fields.items()))
    return _coupon_card(db, coupon)


# ── There is no DELETE, and that is the design ───────────────────────────────
#
# CouponRedemption.coupon_id is ON DELETE CASCADE. Removing one coupon row would
# silently take every redemption attached to it: who paid, what they actually
# paid, and the link to their Payment — a financial record, deleted by a button
# on an admin page, with no way back.
#
# `is_active = false` does the job the client actually wants. preview_coupon and
# _reserve_redemption both refuse an inactive coupon with reason `inactive`, the
# history stays on the panel, and it can be switched back on.
