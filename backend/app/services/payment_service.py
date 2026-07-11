"""
Shared Kashier payment confirmation logic.

Both the server-to-server webhook (`/webhooks/kashier`) and the browser
success redirect (`/payment/kashier/success`) funnel through
`confirm_kashier_payment` so a confirmation is applied exactly once,
no matter which signal arrives first.
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.orm import Session

from app.models import Payment, PaymentStatus, User

logger = logging.getLogger(__name__)

# Egypt timezone — handles DST automatically (UTC+2 winter / UTC+3 summer)
CAIRO_TZ = ZoneInfo("Africa/Cairo")


def to_cairo_iso(dt):
    """Convert a naive-UTC datetime to an Egypt-local ISO 8601 string (with offset).

    The backend stores naive UTC timestamps; the n8n automation expects Egypt
    wall-clock time, so we attach UTC then shift to Africa/Cairo.
    """
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CAIRO_TZ).isoformat()


def plan_duration(plan_key: str):
    """Map a plan_key to (days, duration_type)."""
    days, duration_type = 30, "1_month"
    if plan_key:
        if "yearly" in plan_key:
            days, duration_type = 365, "1_year"
        elif "quarterly" in plan_key:
            days, duration_type = 90, "3_months"
    return days, duration_type


async def send_payment_n8n_webhook(payload: dict):
    """Notify the N8N payment automation. Best-effort, never raises."""
    webhook_url = os.getenv("N8N_PAYMENT_WEBHOOK_URL")
    if not webhook_url:
        logger.warning("⚠️ N8N_PAYMENT_WEBHOOK_URL not configured — skipping notification")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload, timeout=10.0)
            logger.info("✅ Successfully sent payment webhook to N8N")
    except Exception as e:
        logger.error("❌ Failed to send N8N payment webhook: %s", e)


def _build_n8n_payload(user, payment: Payment, duration_type: str, transaction_id: str = ""):
    return {
        "user_id": user.id if user else payment.user_id,
        "user_name": getattr(user, "full_name", "") if user else "",
        "user_email": getattr(user, "email", "") if user else "",
        "user_phone": getattr(user, "phone", "") if user else "",
        "amount": float(payment.amount) if payment.amount else 0.0,
        "currency": payment.currency,
        "order_id": payment.provider_order_id,
        "transaction_id": transaction_id or "",
        "payment_status": "success",
        "payment_method": "kashier",
        "paid_at": to_cairo_iso(payment.confirmed_at or datetime.utcnow()),
        "subscription_duration": duration_type,
    }


def confirm_kashier_payment(db: Session, payment: Payment, source: str,
                            background_tasks=None, transaction_id: str = ""):
    """
    Idempotently confirm a Kashier payment and activate the user's subscription.

    Only a PENDING payment is acted on; calling again on an already-CONFIRMED
    payment is a no-op (so the webhook and the success redirect can't double-apply).

    Returns (user, newly_confirmed).
    """
    days, duration_type = plan_duration(payment.plan_key)
    user = db.query(User).filter(User.id == payment.user_id).first()

    if payment.status != PaymentStatus.PENDING:
        logger.info("ℹ️ Payment %s already %s — skipping (%s)",
                    payment.provider_order_id, payment.status, source)
        return user, False

    payment.status = PaymentStatus.CONFIRMED
    payment.confirmed_at = datetime.utcnow()

    if user:
        # Extend from the later of "now" or the current end date so an early
        # renewal doesn't shorten an active subscription.
        base = user.end_at if (user.end_at and user.end_at > datetime.utcnow()) else datetime.utcnow()
        user.end_at = base + timedelta(days=days)
        user.is_active = True

    db.commit()
    logger.info("✅ Payment CONFIRMED via %s | order=%s | user=%s",
                source, payment.provider_order_id, payment.user_id)

    if background_tasks is not None:
        payload = _build_n8n_payload(user, payment, duration_type, transaction_id)
        background_tasks.add_task(send_payment_n8n_webhook, payload)

    return user, True
