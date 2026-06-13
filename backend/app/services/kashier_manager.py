import hashlib
import hmac
import httpx
import logging
import os
import json
from dotenv import load_dotenv
from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)

KASHIER_MERCHANT_ID = os.getenv("KASHIER_MERCHANT_ID")   # MID-xxx-xxx
KASHIER_API_KEY = os.getenv("KASHIER_API_KEY")
KASHIER_SECRET_KEY = os.getenv("KASHIER_SECRET_KEY")
KASHIER_BASE_URL = os.getenv("KASHIER_BASE_URL", "https://payments.kashier.io")
KASHIER_CURRENCY = os.getenv("KASHIER_CURRENCY", "EGP")
KASHIER_MODE = os.getenv("KASHIER_MODE", "live")

# ── API Base URL (مختلف عن Checkout URL) ──
KASHIER_API_BASE = "https://test-api.kashier.io" if KASHIER_MODE == "test" else "https://api.kashier.io"

# علشان نتاكد ان الرقم هيبقي dec, وبناخد اول رقمين بعد ال dot
def _format_amount(value) -> str:
    """
    Keep amount format stable between create URL and webhook verification.
    """
    try:
        normalized = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        normalized = Decimal("0.00")
    return f"{normalized:.2f}"

def generate_kashier_hash(merchant_id: str, order_id: str, amount: str, currency: str, api_key: str) -> str:
    # Kashier HPP hash format according to docs:
    # /?payment={mid}.{orderId}.{amount}.{currency}
    message = f"/?payment={merchant_id}.{order_id}.{amount}.{currency}"
    
    hash_value = hmac.new(
        api_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return hash_value


async def create_kashier_payment_url(
    order_id: str, 
    amount: float, 
    currency: str = None,
    user_email: str = "",
    user_phone: str = "",
    user_id: int = None
) -> dict:
    """
    إنشاء Payment URL عبر Kashier HPP.
    تم إضافة saveCard و shopperReference مباشرة للـ URL.
    """
    signing_key = KASHIER_API_KEY
    if not KASHIER_MERCHANT_ID or not signing_key:
        raise ValueError("Kashier API credentials are missing.")

    amount_str = _format_amount(amount)
    currency = currency or KASHIER_CURRENCY

    hash_value = generate_kashier_hash(
        KASHIER_MERCHANT_ID, order_id, amount_str, currency, signing_key
    )

    params = {
        "merchantId": KASHIER_MERCHANT_ID,
        "amount": amount_str,
        "currency": currency,
        "orderId": order_id,
        "hash": hash_value,
        "mode": KASHIER_MODE,
        "merchantRedirect": os.getenv("KASHIER_RETURN_URL"),
        "failureRedirect": os.getenv("KASHIER_FAILURE_URL"),
        "serverWebhook": os.getenv("KASHIER_WEBHOOK_URL"),
        "allowedMethods": "card,wallet",
        "display": "ar",
        "customerName": f"User {user_id}" if user_id else "Customer",
        "customerEmail": user_email or "customer@example.com",
        "customerMobile": user_phone or "",
        "merchantCustomerId": str(user_id) if user_id else order_id,
        "customerId": str(user_id) if user_id else order_id,
    }

    query_string = urlencode(params)
    base_url = KASHIER_BASE_URL.rstrip('/') if KASHIER_BASE_URL else "https://payments.kashier.io"
    
    # Kashier's HPP URL is typically checkout.kashier.io or payments.kashier.io
    # For HPP it's best to explicitly use the checkout/payments domain instead of api.kashier.io
    payment_url = f"{base_url}/?{query_string}"

    logger.info("🔗 Generated Kashier HPP URL (with saveCard): %s", payment_url)

    return {
        "payment_url": payment_url,
        "order_id": order_id,
        "amount": amount_str,
        "currency": currency,
    }


def _create_kashier_url_fallback(
    order_id: str, amount_str: str, currency: str, hash_value: str,
    user_email: str, user_id: int
) -> dict:
    """Fallback: بناء الـ URL يدوياً بدون saveCard لو الـ Payment Session فشل."""
    params = {
        "merchantId": KASHIER_MERCHANT_ID,
        "amount": amount_str,
        "currency": currency,
        "orderId": order_id,
        "hash": hash_value,
        "mode": KASHIER_MODE,
        "merchantRedirect": os.getenv("KASHIER_RETURN_URL"),
        "failureRedirect": os.getenv("KASHIER_FAILURE_URL"),
        "serverWebhook": os.getenv("KASHIER_WEBHOOK_URL"),
        "allowedMethods": "card,wallet",
        "display": "ar",
        "customerEmail": user_email or "customer@example.com",
        "customerName": f"User {user_id}" if user_id else "Customer",
    }

    query_string = urlencode(params)
    base_url = KASHIER_BASE_URL.rstrip('/') if KASHIER_BASE_URL else "https://payments.kashier.io"
    payment_url = f"{base_url}/?{query_string}"

    return {
        "payment_url": payment_url,
        "order_id": order_id,
        "amount": amount_str,
        "currency": currency,
    }


def verify_kashier_webhook(data: dict, received_hash: str) -> bool:
    """
    Kashier بيحدد الـ signatureKeys في الـ data نفسه
    """
    # signing_key = KASHIER_SECRET_KEY
    signing_key = KASHIER_API_KEY
    if not signing_key or not received_hash:
        return False
    
    # لو Kashier بعت signatureKeys، استخدمهم
    signature_keys = data.get("signatureKeys", [])
    
    if signature_keys:
        # بنبني الـ message من الـ keys المحددة مرتبة
        parts = []
        for key in signature_keys:
            value = data.get(key, "")
            parts.append(f"{key}={value}")
        message = "&".join(parts)

        logger.info("⚡ Constructed Webhook Message for Hashing: %s", message)
    else:
        # fallback للطريقة القديمة
        order_id = data.get("orderId", "")
        amount = _format_amount(data.get("amount", ""))
        currency = data.get("currency", KASHIER_CURRENCY)
        merchant_id = data.get("merchantId", KASHIER_MERCHANT_ID)
        message = f"/?payment={merchant_id}.{order_id}.{amount}.{currency}"

        signing_key = KASHIER_API_KEY
    
    import hmac as _hmac
    expected = _hmac.new(
        signing_key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return _hmac.compare_digest(expected, received_hash)