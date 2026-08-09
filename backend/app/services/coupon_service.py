"""
Discount coupons — validation, the thirty-slot cap, and redemption bookkeeping.

Everything in this module runs on the SERVER's numbers. A caller hands in a
plan and a string typed by a member; nothing else about price crosses the
boundary. That is the same rule the comment at the top of routers/payment.py
lays down for PLAN_PRICES, and for the same reason: this project has already
shipped a bug where the advertised price and the collected price disagreed
because the number lived in more than one place. A discount percentage arriving
from a browser would be that bug again, wearing a hat.


─── How the cap is enforced ──────────────────────────────────────────────────

`SELECT count(*)` followed by `INSERT` is not enough. Two members paying in the
same instant both read 29, both insert, and the coupon has been used 31 times.

So a redemption is taken under a row lock on the coupon itself:

    SELECT * FROM coupons WHERE id = :id FOR UPDATE   ← serialises everyone
    SELECT count(*) FROM coupon_redemptions ...       ← now authoritative
    INSERT INTO coupon_redemptions ...
    COMMIT                                            ← lock released

The second transaction blocks on the FOR UPDATE until the first commits, and
then counts 30, not 29. The lock is held for a few hundred microseconds of
arithmetic — no network call happens inside it.

On top of that, `slot_no` is assigned under the same lock and carries a unique
index on (coupon_id, slot_no). If the lock were ever bypassed — a stray session,
a future code path that forgets — two inserts claiming slot 30 collide on the
index and one of them rolls back. The limit is a property of the schema, not of
anybody remembering to write an `if`.


─── When a slot is taken, and when it comes back ─────────────────────────────

The brief poses the real dilemma: count at checkout START and an abandoned tab
burns one of the thirty; count only at CONFIRMATION and a hundred people can
start with the code and all of them finish.

This module takes a third option — a hold with a deadline:

  Kashier, order created   → PENDING hold, expires in 30 minutes. It counts
                             against the cap while it lives, so a hundred
                             simultaneous checkouts cannot all be discounted;
                             and it stops counting when it lapses, so a tab left
                             open costs the coupon half an hour, not a slot.
  Kashier, payment CONFIRMED → the hold becomes ACTIVE and permanent.
  Instapay, receipt submitted → ACTIVE straight away. There is no dilemma here:
                             the member has already moved the money by hand.
  Instapay, request REJECTED → RELEASED. The slot returns to the pool, the row
                             stays for the record, and the member may use the
                             code again — being rejected over a blurry
                             screenshot should not cost them the discount.
  Instapay, request APPROVED → stays ACTIVE.


─── The rule that outranks the cap ───────────────────────────────────────────

Never fail a payment over a coupon. `confirm_redemption` below cannot raise and
cannot refuse: if the thirty filled up while a member sat on the Kashier page,
the payment they already made is confirmed at the price they were quoted, the
redemption is recorded, and the overflow is written to the log for someone to
look at. Thirty-one discounts is a bad afternoon; charging someone and then
refusing to let them in is a lost customer and a support ticket that is right.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from app.models import Coupon, CouponRedemption, CouponRedemptionStatus

logger = logging.getLogger(__name__)

# How long an unpaid Kashier order keeps its claim on a slot. Long enough to
# read a card number off a card and deal with a 3-D Secure SMS; short enough
# that a closed tab is forgotten about within the hour.
PENDING_HOLD_MINUTES = 30

# Machine-readable reasons. The frontend never invents these — it renders the
# one the backend sends, which is what keeps the two from disagreeing about
# whether a coupon worked.
REASON_OK = "ok"
REASON_NOT_FOUND = "not_found"
REASON_INACTIVE = "inactive"
REASON_EXHAUSTED = "exhausted"
REASON_ALREADY_USED = "already_used"
# Something in here broke. The member is not told a story about their code —
# they are quietly charged the correct full price and the exception is logged.
REASON_ERROR = "error"

# Arabic first because the pages that show these are Arabic first; the frontend
# carries its own bilingual copy and uses `reason`, so these are the fallback
# for anything that only reads `message`.
REASON_MESSAGES = {
    REASON_NOT_FOUND:    "الكود غلط",
    REASON_INACTIVE:     "الكوبون ده مش شغال دلوقتي",
    REASON_EXHAUSTED:    "الكوبون ده خلص",
    REASON_ALREADY_USED: "إنت مستخدم الكوبون ده قبل كده",
    REASON_ERROR:        "مقدرناش نطبّق الكوبون دلوقتي",
}


def normalize_code(raw: Optional[str]) -> str:
    """`  Monzer ` → `monzer`. Case and stray spaces are not part of a code."""
    return (raw or "").strip().lower()


def apply_percent(amount, percent) -> Decimal:
    """The discounted price, to two decimals, rounded half-up.

    Money arithmetic in Decimal rather than float: 3500 * 0.9 is 3150.0000000004
    in binary floating point on some inputs, and this number goes into a Kashier
    HMAC where a trailing digit is the difference between a valid signature and
    a rejected order.
    """
    base = Decimal(str(amount))
    pct = Decimal(str(percent))
    factor = (Decimal("100") - pct) / Decimal("100")
    return (base * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _live_redemption_filter(coupon_id: int, now: datetime):
    """Rows that currently occupy one of the coupon's slots.

    ACTIVE always counts. PENDING counts only until its hold lapses — an
    expired hold is a checkout nobody finished and must not hold the coupon
    hostage. EXPIRED and RELEASED never count.
    """
    return and_(
        CouponRedemption.coupon_id == coupon_id,
        or_(
            CouponRedemption.status == CouponRedemptionStatus.ACTIVE.value,
            and_(
                CouponRedemption.status == CouponRedemptionStatus.PENDING.value,
                CouponRedemption.expires_at > now,
            ),
        ),
    )


def count_live_redemptions(db: Session, coupon_id: int, now: Optional[datetime] = None) -> int:
    now = now or datetime.utcnow()
    return db.query(CouponRedemption).filter(_live_redemption_filter(coupon_id, now)).count()


def _reclaim_expired(db: Session, coupon_id: int, now: datetime) -> int:
    """Retire lapsed holds so they let go of their slot numbers.

    A hold that has passed its deadline already stops counting toward the cap —
    `_live_redemption_filter` ignores it. But until this runs it is still
    sitting on a `slot_no`, and that is the difference between "stops counting"
    and "actually freed".

    This is the bug that made the first version of this module hand a customer a
    500. Someone opened a discounted checkout and wandered off; half an hour
    later their hold stopped counting, so the next member was computed to be
    number 1 — a number the abandoned row still owned. The insert hit
    uq_coupon_redemption_slot and the payment page broke, for a member who had
    done nothing wrong, because of a stranger's abandoned tab.

    Called under the coupon's row lock, which is the only place it is safe: no
    other transaction can be reading the count while these rows change hands.
    There is no background job, and deliberately so — the lock is taken on every
    path that cares, so the reclaim happens exactly when it matters and never
    on a schedule that could run at the wrong moment.
    """
    stale = db.query(CouponRedemption).filter(
        CouponRedemption.coupon_id == coupon_id,
        CouponRedemption.status == CouponRedemptionStatus.PENDING.value,
        CouponRedemption.expires_at <= now,
    ).all()
    for r in stale:
        r.status = CouponRedemptionStatus.EXPIRED.value
        r.slot_no = None
    if stale:
        db.flush()
        logger.info("🎟️ Reclaimed %s lapsed hold(s) on coupon %s", len(stale), coupon_id)
    return len(stale)


def _next_slot(db: Session, coupon_id: int) -> int:
    """The lowest slot number nobody is holding.

    Not `count + 1`. As soon as any slot is handed back — a rejected manual
    request, a lapsed hold — the number of live redemptions and the highest
    number in use stop agreeing, and count+1 starts naming a slot that is
    already taken. Lowest-free is stable under both, and it keeps the numbers
    meaning what they look like: slot 7 is the seventh of the thirty.

    Must be called under the coupon's row lock; the unique index is what catches
    it if it ever is not.
    """
    taken = {
        s for (s,) in db.query(CouponRedemption.slot_no).filter(
            CouponRedemption.coupon_id == coupon_id,
            CouponRedemption.slot_no.isnot(None),
        ).all()
    }
    n = 1
    while n in taken:
        n += 1
    return n


def get_coupon(db: Session, raw_code: str) -> Optional[Coupon]:
    code = normalize_code(raw_code)
    if not code:
        return None
    return db.query(Coupon).filter(Coupon.code == code).first()


def _result(applied: bool, reason: str, coupon=None, original=None, final=None, remaining=None):
    """The one shape every coupon answer takes, on every route.

    `applied` is the only field the caller needs to branch on; `reason` is what
    the member gets told. A refusal is never an exception — a wrong code has to
    fall through to the full price, not abort a checkout.
    """
    out = {
        "applied": applied,
        "reason": reason,
        "message": REASON_MESSAGES.get(reason, ""),
        "code": coupon.label if coupon else None,
        "discount_percent": float(coupon.discount_percent) if coupon else None,
        "original_amount": float(original) if original is not None else None,
        "final_amount": float(final) if final is not None else None,
        "remaining": remaining,
    }
    return out


def preview_coupon(db: Session, raw_code: str, user_id: int, amount, currency: str = "EGP") -> dict:
    """Answer "what would this code do?" without touching a slot.

    Behind the Apply button on /pricing and /pay. Read-only on purpose: a member
    trying a code out must not consume anything, and the authoritative decision
    is taken again — under the lock — when they actually pay.
    """
    coupon = get_coupon(db, raw_code)
    if not coupon:
        return _result(False, REASON_NOT_FOUND)
    if not coupon.is_active:
        return _result(False, REASON_INACTIVE, coupon)

    now = datetime.utcnow()

    existing = db.query(CouponRedemption).filter(
        CouponRedemption.coupon_id == coupon.id,
        CouponRedemption.user_id == user_id,
        CouponRedemption.status.in_(CouponRedemptionStatus.holding()),
    ).first()
    # A live hold of their own is this member resuming their own checkout, not a
    # second bite. Only a spent one blocks.
    if existing and existing.status == CouponRedemptionStatus.ACTIVE.value:
        return _result(False, REASON_ALREADY_USED, coupon)

    used = count_live_redemptions(db, coupon.id, now)
    remaining = max(0, coupon.max_redemptions - used)
    if remaining <= 0 and not existing:
        return _result(False, REASON_EXHAUSTED, coupon, remaining=0)

    final = apply_percent(amount, coupon.discount_percent)
    return _result(True, REASON_OK, coupon, original=Decimal(str(amount)), final=final, remaining=remaining)


def reserve_redemption(
    db: Session,
    raw_code: str,
    user_id: int,
    amount,
    currency: str = "EGP",
    plan_key: Optional[str] = None,
    hold: bool = True,
) -> dict:
    """Take a slot and return the price to charge. **Never raises, ever.**

    `hold=True`  (Kashier) — a PENDING claim with a deadline; confirm it later.
    `hold=False` (Instapay) — ACTIVE immediately, because the money has moved.

    Two things the caller must know:

      - Do NOT commit between calling this and writing your own row. The lock
        taken here is what makes the count authoritative, and it lives until
        your commit.
      - Call this BEFORE writing anything else to the session. If the coupon
        work fails, this rolls the session back and reports applied=False so the
        caller can carry on at full price — and a rollback would take any
        earlier writes with it.

    The blanket except is the golden rule in code form. A coupon is a discount,
    not a prerequisite: whatever goes wrong in here, the customer must still be
    able to buy the thing. Both callers read `applied` and fall through to the
    list price, so a failure costs the member 10% and costs us a log line,
    rather than costing us the sale.
    """
    try:
        return _reserve_redemption(db, raw_code, user_id, amount, currency, plan_key, hold)
    except Exception:
        logger.exception("🎟️❌ Coupon reservation failed for user %s (code=%r) — "
                         "continuing at full price", user_id, raw_code)
        try:
            db.rollback()
        except Exception:
            logger.exception("🎟️❌ Rollback after a failed coupon reservation also failed")
        return _result(False, REASON_ERROR)


def _reserve_redemption(
    db: Session,
    raw_code: str,
    user_id: int,
    amount,
    currency: str,
    plan_key: Optional[str],
    hold: bool,
) -> dict:
    coupon = get_coupon(db, raw_code)
    if not coupon:
        return _result(False, REASON_NOT_FOUND)

    # 🔒 The cap lives here. Serialise every attempt on this coupon before
    # counting anything — see the module docstring.
    locked = db.query(Coupon).filter(Coupon.id == coupon.id).with_for_update().first()
    if not locked:
        return _result(False, REASON_NOT_FOUND)
    if not locked.is_active:
        return _result(False, REASON_INACTIVE, locked)

    now = datetime.utcnow()

    # Retire anyone else's lapsed holds first, so the count and the slot numbers
    # below are describing the same reality. See _reclaim_expired.
    _reclaim_expired(db, locked.id, now)

    existing = db.query(CouponRedemption).filter(
        CouponRedemption.coupon_id == locked.id,
        CouponRedemption.user_id == user_id,
        CouponRedemption.status.in_(CouponRedemptionStatus.holding()),
    ).first()

    if existing and existing.status == CouponRedemptionStatus.ACTIVE.value:
        return _result(False, REASON_ALREADY_USED, locked)

    final = apply_percent(amount, locked.discount_percent)

    if existing:
        # Their own unfinished checkout. Refresh it rather than insert a second
        # row — the partial unique index would refuse the insert anyway, and the
        # member switching plan or coming back an hour later is normal.
        existing.original_amount = Decimal(str(amount))
        existing.final_amount = final
        existing.currency = currency
        existing.plan_key = plan_key
        if hold:
            existing.expires_at = now + timedelta(minutes=PENDING_HOLD_MINUTES)
        else:
            existing.status = CouponRedemptionStatus.ACTIVE.value
            existing.expires_at = None
            existing.confirmed_at = now
        db.flush()
        used = count_live_redemptions(db, locked.id, now)
        return _result(True, REASON_OK, locked, original=Decimal(str(amount)), final=final,
                       remaining=max(0, locked.max_redemptions - used))

    used = count_live_redemptions(db, locked.id, now)
    if used >= locked.max_redemptions:
        logger.info("🎟️ Coupon %s exhausted (%s/%s) — user %s pays full price",
                    locked.code, used, locked.max_redemptions, user_id)
        return _result(False, REASON_EXHAUSTED, locked, remaining=0)

    redemption = CouponRedemption(
        coupon_id=locked.id,
        user_id=user_id,
        status=(CouponRedemptionStatus.PENDING.value if hold else CouponRedemptionStatus.ACTIVE.value),
        slot_no=_next_slot(db, locked.id),
        original_amount=Decimal(str(amount)),
        final_amount=final,
        currency=currency,
        plan_key=plan_key,
        expires_at=(now + timedelta(minutes=PENDING_HOLD_MINUTES) if hold else None),
        confirmed_at=(None if hold else now),
    )
    db.add(redemption)
    db.flush()  # surface a slot_no collision here, still inside the caller's transaction

    logger.info("🎟️ Coupon %s reserved slot %s/%s for user %s (%s → %s %s)",
                locked.code, redemption.slot_no, locked.max_redemptions, user_id,
                amount, final, currency)

    out = _result(True, REASON_OK, locked, original=Decimal(str(amount)), final=final,
                  remaining=max(0, locked.max_redemptions - (used + 1)))
    out["_redemption"] = redemption
    return out


def attach_payment(db: Session, result: dict, payment_id: int):
    """Point the redemption we just took at the Payment row it paid for."""
    redemption = result.get("_redemption") if result else None
    if redemption is not None:
        redemption.payment_id = payment_id
        db.flush()


def link_manual_request(db: Session, code: str, user_id: int, request_id: int) -> None:
    """Point an existing redemption at the manual request it belongs to.

    Needed for the case where reserve_redemption refreshed a row this member
    already had (an abandoned card checkout, say) instead of inserting a new
    one, so there was no fresh object to hang the request id on. Without this
    the redemption keeps a stale payment_id and a rejection would never find it
    to release the slot.
    """
    coupon = get_coupon(db, code)
    if not coupon:
        return
    redemption = db.query(CouponRedemption).filter(
        CouponRedemption.coupon_id == coupon.id,
        CouponRedemption.user_id == user_id,
        CouponRedemption.status.in_(CouponRedemptionStatus.holding()),
    ).first()
    if redemption is not None:
        redemption.manual_request_id = request_id
        redemption.payment_id = None
        db.flush()


def confirm_redemption(db: Session, payment) -> None:
    """A Kashier payment cleared — make its hold permanent.

    Called from inside confirm_kashier_payment, before its commit.

    This function does not refuse and does not raise. If the hold lapsed while
    the member was on the payment page and the coupon has since filled up, the
    redemption is still recorded — they were quoted a price and they paid it —
    and the overflow goes in the log. See the last section of the module
    docstring for why that is the right way round.
    """
    try:
        # PENDING *or* EXPIRED. A hold that lapsed while the member was on the
        # Kashier page has usually been reclaimed by someone else's request by
        # the time the money lands — and that member has still paid, so their
        # redemption is still theirs to record.
        redemption = db.query(CouponRedemption).filter(
            CouponRedemption.payment_id == payment.id,
            CouponRedemption.status.in_([
                CouponRedemptionStatus.PENDING.value,
                CouponRedemptionStatus.EXPIRED.value,
            ]),
        ).first()
        if not redemption:
            return

        now = datetime.utcnow()
        was_reclaimed = redemption.status == CouponRedemptionStatus.EXPIRED.value

        coupon = db.query(Coupon).filter(Coupon.id == redemption.coupon_id).first()
        if coupon:
            live = count_live_redemptions(db, coupon.id, now)
            lapsed = was_reclaimed or (redemption.expires_at is not None and redemption.expires_at <= now)
            if lapsed and live >= coupon.max_redemptions:
                logger.warning(
                    "🎟️⚠️ Coupon %s is over its limit (%s/%s) but order %s already paid at "
                    "the discounted price — honouring it.",
                    coupon.code, live + 1, coupon.max_redemptions,
                    payment.provider_order_id,
                )

        redemption.status = CouponRedemptionStatus.ACTIVE.value
        redemption.expires_at = None
        redemption.confirmed_at = now
        # A reclaimed hold gave up its number on the way out and needs a fresh
        # one. _next_slot picks the lowest free, which may land above the cap
        # when this is the honoured overflow — that is the intended outcome, and
        # it cannot collide, so it cannot fail the confirmation.
        if redemption.slot_no is None:
            redemption.slot_no = _next_slot(db, redemption.coupon_id)
        logger.info("🎟️ Coupon redemption %s confirmed for order %s (slot %s%s)",
                    redemption.id, payment.provider_order_id, redemption.slot_no,
                    ", hold had lapsed" if was_reclaimed else "")
    except Exception:
        # A coupon must never be the reason a paid subscription fails to
        # activate. Log it and let the confirmation finish.
        logger.exception("🎟️❌ Could not confirm coupon redemption for payment %s — "
                         "payment confirmation continues regardless", getattr(payment, "id", "?"))


def release_for_manual_request(db: Session, request_id: int) -> None:
    """A manual request was rejected — hand its slot back.

    `slot_no` is cleared as well as the status: the number has to be free for
    the next member, and the unique index on (coupon_id, slot_no) would
    otherwise keep it reserved for a redemption that no longer counts.
    """
    try:
        redemption = db.query(CouponRedemption).filter(
            CouponRedemption.manual_request_id == request_id,
            CouponRedemption.status != CouponRedemptionStatus.RELEASED.value,
        ).first()
        if not redemption:
            return
        redemption.status = CouponRedemptionStatus.RELEASED.value
        redemption.slot_no = None
        redemption.expires_at = None
        redemption.released_at = datetime.utcnow()
        logger.info("🎟️ Coupon redemption %s released — manual request %s was rejected",
                    redemption.id, request_id)
    except Exception:
        logger.exception("🎟️❌ Could not release coupon redemption for manual request %s", request_id)
