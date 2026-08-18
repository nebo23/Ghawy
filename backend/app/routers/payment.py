from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_
from urllib.parse import parse_qsl
import os
from datetime import datetime
from app.models import Payment, PaymentMethod, PaymentStatus, User
from app.schemas import PaymentOut, KashierCreateOrder, KashierOrderOut
from app.routers.users import get_current_user
from app.database import get_db
from app.services.kashier_manager import verify_kashier_redirect_signature
from app.services.payment_service import confirm_kashier_payment
from app.services import coupon_service

router = APIRouter(prefix="/payment", tags=["Payment"])

# ─── Server-side authoritative pricing ─────────────────────
# Frontend prices in payment.js are display-only. These are the SOURCE OF TRUTH.
# Any mismatch between this dict and frontend pricing means the frontend is stale.
#
# EGP only. There used to be three more rows here — monthly/quarterly/yearly_usd
# — shown to visitors an IP lookup placed outside Egypt. In the whole history of
# the table not one USD order was ever confirmed (89 of them, all abandoned at
# the gateway), and the platform now quotes one price list, in Egyptian pounds,
# to everybody. The keys are gone rather than merely unlinked so a stale cached
# page cannot open a dollar checkout: an old `*_usd` plan_key falls into the
# "Invalid plan" branch below.
PLAN_PRICES = {
    "monthly_egp":   {"amount": 600,   "currency": "EGP"},
    "quarterly_egp": {"amount": 1200,  "currency": "EGP"},
    "yearly_egp":    {"amount": 3500,  "currency": "EGP"},
}


from app.services.kashier_manager import create_kashier_payment_url
import uuid
import logging

logger = logging.getLogger(__name__)

# ─── Kashier: إنشاء أوردر ────────────────────────────────────
@router.post("/kashier/create")
async def kashier_create(data: KashierCreateOrder, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # 🔒 السعر يتحدد server-side فقط — أي amount/currency من الـ frontend بيتم تجاهلهم
    if data.plan_key not in PLAN_PRICES:
        logger.warning("🚨 Invalid plan_key from user %s: %s", current_user.id, data.plan_key)
        raise HTTPException(status_code=400, detail="Invalid plan")

    plan = PLAN_PRICES[data.plan_key]
    list_amount = plan["amount"]
    server_currency = plan["currency"]

    # ── Coupon ──────────────────────────────────────────────────
    # `data.coupon_code` is a NAME, and that is the only thing about a discount
    # that crosses the wire. The percentage and the resulting price are read
    # from the coupons table and computed here, next to PLAN_PRICES, for exactly
    # the reason written at the top of this file.
    #
    # A code that is wrong, switched off, already used by this member or down to
    # its last slot does NOT fail the request. It falls through to the full
    # price and the answer carries `coupon` so the page can say why before it
    # sends anyone to Kashier. Refusing to sell to someone because they mistyped
    # a coupon would be a strange way to run a shop.
    #
    # reserve_redemption takes a row lock on the coupon and holds it until the
    # commit below, so the count it based its decision on cannot have moved
    # underneath it. Nothing between here and that commit does network I/O —
    # create_kashier_payment_url only builds and signs a URL.
    coupon_result = None
    if (data.coupon_code or "").strip():
        coupon_result = coupon_service.reserve_redemption(
            db,
            raw_code=data.coupon_code,
            user_id=current_user.id,
            amount=list_amount,
            currency=server_currency,
            plan_key=data.plan_key,
            hold=True,
        )

    server_amount = float(coupon_result["final_amount"]) if (coupon_result and coupon_result["applied"]) else list_amount

    # NOTE: We intentionally do NOT delete the user's old PENDING Kashier payments here.
    # A payment can be SUCCESSful at Kashier while still PENDING on our side (e.g. the
    # webhook is delayed or was missed). Deleting it on the next "Pay" click would erase
    # the only record of a real, paid order and permanently strand that customer.
    # Stale pending rows are harmless; they get confirmed when their webhook/redirect
    # arrives, or can be cleaned up by an admin.
    order_id = f"ORD-{current_user.id}-{uuid.uuid4().hex[:8].upper()}"

    result = await create_kashier_payment_url(
        order_id=order_id,
        amount=server_amount,
        currency=server_currency,
        user_email=current_user.email,
        user_phone=current_user.phone,
        user_id=current_user.id,
    )

    payment = Payment(
        user_id=current_user.id,
        method=PaymentMethod.KASHIER,
        # The DISCOUNTED figure, which is also the figure inside the Kashier
        # hash. _redirect_amounts_match() below compares what Kashier reports
        # back against this column, so storing the list price here instead would
        # make every discounted payment fail its amount check and sit
        # unconfirmed. That is the single most breakable thing in this change.
        amount=server_amount,
        currency=server_currency,
        provider_order_id=order_id,
        plan_key=data.plan_key,
        status=PaymentStatus.PENDING,
    )
    db.add(payment)
    db.flush()  # need the id to link the redemption, still inside the lock

    if coupon_result and coupon_result["applied"]:
        coupon_service.attach_payment(db, coupon_result, payment.id)

    db.commit()  # releases the coupon row lock

    if coupon_result:
        result["coupon"] = {
            "applied": coupon_result["applied"],
            "reason": coupon_result["reason"],
            "message": coupon_result["message"],
            "code": coupon_result["code"],
            "discount_percent": coupon_result["discount_percent"],
            "original_amount": float(list_amount),
            "final_amount": float(server_amount),
        }
    return result

# ─── Kashier: بعد ما يرجع من صفحة الدفع ─────────────────────
@router.get("/kashier/success")
def kashier_success(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Kashier redirects the customer's browser here after payment with:
    - orderId = Kashier internal UUID
    - merchantOrderId = our order ID (ORD-56-XXXX)
    - paymentStatus, amount, currency, ... and a `signature` over those params.

    This redirect is the PRIMARY confirmation path for the customer: we validate
    the signature and (idempotently) confirm the payment here, so the user is
    activated and can enter onboarding even if the server webhook was missed.
    """
    # Preserve the exact param order from the URL — the signature depends on it.
    query_pairs = parse_qsl(request.url.query, keep_blank_values=True)
    params = dict(query_pairs)

    order_id = params.get("merchantOrderId") or params.get("orderId")
    payment_status = (params.get("paymentStatus") or "").upper()

    redirect_page = "onboarding.html"

    if order_id:
        payment = db.query(Payment).filter(
            Payment.method == PaymentMethod.KASHIER,
            or_(
                Payment.provider_order_id == params.get("merchantOrderId"),
                Payment.provider_order_id == params.get("orderId"),
            )
        ).first()

        if payment:
            if (
                payment.status == PaymentStatus.PENDING
                and payment_status == "SUCCESS"
                and verify_kashier_redirect_signature(query_pairs)
                and _redirect_amounts_match(params, payment)
            ):
                confirm_kashier_payment(
                    db, payment, source="redirect",
                    background_tasks=background_tasks,
                    transaction_id=params.get("transactionId", ""),
                )
            elif payment.status == PaymentStatus.PENDING:
                logger.warning(
                    "⚠️ Success redirect for order %s not confirmed (status=%s, sig/amount check failed) — awaiting webhook",
                    order_id, payment_status,
                )

            user = db.query(User).filter(User.id == payment.user_id).first()
            if user and user.onboarding_completed:
                redirect_page = "dashboard.html"

    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    return RedirectResponse(url=f"{frontend_url}/{redirect_page}")


def _redirect_amounts_match(params: dict, payment: Payment) -> bool:
    """Cross-check the amount/currency in the redirect against the stored order."""
    currency = (params.get("currency") or "").upper()
    if currency and currency != (payment.currency or "").upper():
        logger.error("🚨 Redirect currency mismatch! order=%s stored=%s got=%s",
                     payment.provider_order_id, payment.currency, currency)
        return False
    amount_raw = params.get("amount")
    if amount_raw is not None:
        try:
            if abs(float(amount_raw) - float(payment.amount)) > 0.01:
                logger.error("🚨 Redirect amount mismatch! order=%s stored=%s got=%s",
                             payment.provider_order_id, payment.amount, amount_raw)
                return False
        except (ValueError, TypeError):
            return False
    return True

# ─── Kashier: لو فشل الدفع ───────────────────────────────────
@router.get("/kashier/fail")
def kashier_fail():
    frontend_url = os.getenv("FRONTEND_URL", "https://ghawy.ai")
    # Back to the plans page with the failure flagged. /pricing replaced
    # /payment, and unlike the old page it actually reads `error` and says
    # something — see the ?error=failed handler in pricing.html.
    return RedirectResponse(url=f"{frontend_url}/pricing?error=failed")
