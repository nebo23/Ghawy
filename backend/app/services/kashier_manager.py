import hashlib
import hmac
import httpx
import logging
import os
import json
from dotenv import load_dotenv
from urllib.parse import urlencode, quote
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

    # Egyptian mobile wallets (Vodafone Cash, etc.) settle in EGP only — offering
    # them on a non-EGP order makes Kashier reject/error the checkout. Restrict to
    # card-only for any currency other than EGP.
    allowed_methods = "card,wallet" if currency.upper() == "EGP" else "card"

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
        "allowedMethods": allowed_methods,
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
    allowed_methods = "card,wallet" if currency.upper() == "EGP" else "card"
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
        "allowedMethods": allowed_methods,
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


def _rfc3986(value) -> str:
    """
    Percent-encode like PHP's rawurlencode / http_build_query(PHP_QUERY_RFC3986)
    and JS encodeURIComponent: keep only A-Za-z0-9 and -_.~, encode everything else.
    """
    return quote(str(value), safe="-_.~")


def verify_kashier_webhook(data: dict, received_signature: str) -> bool:
    """
    Validate the Kashier **server webhook** signature.

    Kashier sends the signature in the `x-kashier-signature` HTTP header (NOT the
    body `hash` field). It is computed over the fields named in `data.signatureKeys`,
    sorted, encoded as an RFC3986 query string, and HMAC-SHA256'd with the Payment
    API key. See https://developers.kashier.io/payment/webhook/
    """
    if not received_signature:
        return False
    signing_key = KASHIER_API_KEY
    if not signing_key:
        logger.error("❌ KASHIER_API_KEY missing — cannot verify webhook signature")
        return False

    sig_keys = data.get("signatureKeys") or []
    if not sig_keys:
        logger.error("❌ Webhook payload has no signatureKeys")
        return False

    query = "&".join(f"{_rfc3986(k)}={_rfc3986(data.get(k, ''))}" for k in sorted(sig_keys))
    expected = hmac.new(signing_key.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(expected, received_signature)
    if not ok:
        logger.error("❌ Webhook signature mismatch | computed=%s | received=%s | payload=%s",
                     expected, received_signature, query)
    return ok


def verify_kashier_redirect_signature(query_pairs) -> bool:
    """
    Validate the Kashier **merchantRedirect** (success/fail) signature.

    `query_pairs` must be the ordered list of (key, value) tuples exactly as they
    appeared in the redirect URL's query string. The signature (the `signature`
    param) is HMAC-SHA256, with the Payment API key, of every other param joined
    raw (no URL-encoding) as `key=value` with `&`, excluding `signature` and `mode`.
    """
    signing_key = KASHIER_API_KEY
    if not signing_key:
        logger.error("❌ KASHIER_API_KEY missing — cannot verify redirect signature")
        return False

    received = None
    parts = []
    for k, v in query_pairs:
        if k == "signature":
            received = v
            continue
        if k == "mode":
            continue
        parts.append(f"{k}={v}")

    if not received:
        return False

    message = "&".join(parts)
    expected = hmac.new(signing_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    ok = hmac.compare_digest(expected, received)
    if not ok:
        logger.error("❌ Redirect signature mismatch | computed=%s | received=%s | payload=%s",
                     expected, received, message)
    return ok