"""
Recurring charge service — charges users with saved card tokens via Kashier.
"""
import httpx
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models import User, Payment, PaymentMethod, PaymentStatus
from app.services.kashier_manager import (
    generate_kashier_hash,
    _format_amount,
    KASHIER_MERCHANT_ID,
    KASHIER_API_KEY,
    KASHIER_SECRET_KEY,
    KASHIER_MODE,
)

logger = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────
MONTHLY_AMOUNT = "500.00"
YEARLY_AMOUNT = "3996.00"
KASHIER_BASE_URL = "https://api.kashier.io"
# 💡 Endpoint لشحن كارت محفوظ (token-based recurring charge):
KASHIER_CHARGE_URL = "https://test-iframe.kashier.io/checkout" if KASHIER_MODE == "test" else "https://iframe.kashier.io/checkout"


async def charge_user(user: User, db: Session) -> bool:
    """Charge a single user using their saved card token."""
    amount = MONTHLY_AMOUNT if user.subscription_type == "monthly" else YEARLY_AMOUNT
    order_id = f"REC-{user.id}-{int(datetime.utcnow().timestamp())}"
    currency = "EGP"
    signing_key = KASHIER_API_KEY or KASHIER_SECRET_KEY

    hash_value = generate_kashier_hash(
        KASHIER_MERCHANT_ID, order_id, amount, currency, signing_key
    )

    payload = {
        "merchantId": KASHIER_MERCHANT_ID,
        "shopper_reference": user.shopper_reference,
        "cardToken": user.card_token,
        "ccvToken": user.ccv_token,
        "amount": amount,
        "currency": currency,
        "display": "en",
        "hash": hash_value,
        "orderId": order_id,
        "serviceName": "customizableForm",
    }


    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(KASHIER_CHARGE_URL, json=payload)
            try:
                result = response.json()
            except ValueError:
                logger.error("❌ API returned non-JSON. Status: %s, Body: %s", response.status_code, response.text)
                return False

        if result.get("status") == "SUCCESS":
            user.failed_charge_count = 0  # reset on success
            # Count existing recurring payments for cycle number
            cycle = (
                db.query(Payment)
                .filter(
                    Payment.user_id == user.id,
                    Payment.is_recurring == True,
                )
                .count()
            )

            # Create payment record
            new_payment = Payment(
                user_id=user.id,
                method=PaymentMethod.KASHIER,
                amount=float(amount),
                currency=currency,
                provider_order_id=order_id,
                status=PaymentStatus.CONFIRMED,
                confirmed_at=datetime.utcnow(),
                is_recurring=True,
                recurring_cycle=cycle + 1,
            )
            db.add(new_payment)

            # Update user subscription dates
            # days_to_add = 30 if user.subscription_type == "monthly" else 365
            user.last_charged_at = datetime.utcnow()
            user.next_charge_at = datetime.utcnow() + timedelta(minutes=2)
            user.subscription_end = user.next_charge_at
            db.commit()

            logger.info(
                "✅ Recurring charge SUCCESS | user_id=%s email=%s amount=%s EGP timestamp=%s cycle=%s",
                user.id, user.email, amount, datetime.utcnow().isoformat(), cycle + 1
            )
            return True

        else:
            logger.warning(
                "❌ Recurring charge FAILED | user_id=%s email=%s amount=%s EGP result=%s timestamp=%s",
                user.id, user.email, amount, result, datetime.utcnow().isoformat(),
            )
            user.failed_charge_count = (user.failed_charge_count or 0) + 1
            if user.failed_charge_count >= 3:
                user.is_active = False
                logger.warning("🚫 User %s deactivated after 3 failed charges", user.id)
            db.commit()
            return False

    except Exception as e:
        logger.error(
            "💥 Recurring charge EXCEPTION | user_id=%s email=%s error=%s timestamp=%s",
            user.id, user.email, e, datetime.utcnow().isoformat(),
        )
        return False


async def run_recurring_charges(db: Session) -> dict:
    """Find all users due for charge and charge them."""
    now = datetime.utcnow()

    users_due = (
        db.query(User)
        .filter(
            User.card_token.isnot(None),
            User.card_token != "",
            User.is_active == True,
            User.next_charge_at.isnot(None),
            User.next_charge_at <= now,
        )
        .all()
    )

    results = {"charged": 0, "failed": 0, "skipped": 0, "total_due": len(users_due), "timestamp": datetime.utcnow().isoformat()}
    logger.info("🔄 Running recurring charges: %d users due", len(users_due))

    for user in users_due:
        success = await charge_user(user, db)
        if success:
            results["charged"] += 1
        else:
            results["failed"] += 1

    logger.info("🔄 Recurring charges complete: %s", results)
    return results
