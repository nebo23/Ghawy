import hashlib
import hmac
import os
from dotenv import load_dotenv
from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

KASHIER_MERCHANT_ID = os.getenv("KASHIER_MERCHANT_ID")   # MID-xxx-xxx
KASHIER_API_KEY = os.getenv("KASHIER_API_KEY")
KASHIER_SECRET_KEY = os.getenv("KASHIER_SECRET_KEY")
KASHIER_BASE_URL = os.getenv("KASHIER_BASE_URL", "https://api.kashier.io")  # sandbox - غيّرها لـ live
KASHIER_CURRENCY = os.getenv("KASHIER_CURRENCY", "EGP")
KASHIER_MODE = os.getenv("KASHIER_MODE", "test")


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

def create_kashier_payment_url(
    order_id: str, 
    amount: float, 
    user_email: str = "",
    user_id: int = None  # ← أضف ده
) -> dict:
    
    amount_str = _format_amount(amount)
    currency = KASHIER_CURRENCY
    signing_key = KASHIER_API_KEY or KASHIER_SECRET_KEY

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
        "allowedMethods": "card,wallet,bank_installments",
        "display": "ar",   # اللغة العربية
        # ── Recurring / Tokenization ──────────────────
        "shopper_reference": f"user_{user_id}" if user_id else f"user_{order_id}",
        "allow_tokenization": "true",
        # ─────────────────────────────────────────────
    }

    # بناء الـ URL
    query_string = urlencode(params)
    payment_url = f"https://payments.kashier.io/?{query_string}"
    # payment_url = f"{KASHIER_BASE_URL}/payment?{query_string}"

    return {
        "payment_url": payment_url,
        "order_id": order_id,
        "amount": amount_str,
        "currency": currency,
    }

def verify_kashier_webhook(payload: dict, received_signature: str) -> bool:
    """
    بتتحقق إن الـ webhook جاي من Kashier فعلاً ومش مزوّر
    """
    order_id = payload.get("orderId", "")
    amount = payload.get("amount", "")
    currency = payload.get("currency", KASHIER_CURRENCY)
    merchant_id = payload.get("merchantId", KASHIER_MERCHANT_ID)

    signing_key = KASHIER_API_KEY or KASHIER_SECRET_KEY
    if not signing_key:
        return False

    expected = generate_kashier_hash(merchant_id, order_id, _format_amount(amount), currency, signing_key)
    return hmac.compare_digest(expected, received_signature)