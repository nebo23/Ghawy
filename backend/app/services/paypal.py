import httpx
import os
from dotenv import load_dotenv
from typing import Any, Dict
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_BASE_URL = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")  # sandbox للتجربة
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID")

async def get_paypal_access_token() -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PAYPAL_BASE_URL}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        )
        response.raise_for_status()
        return response.json()["access_token"]

async def create_paypal_order(amount: float, currency: str = "USD") -> dict:
    token = await get_paypal_access_token()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PAYPAL_BASE_URL}/v2/checkout/orders",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "intent": "CAPTURE",
                "purchase_units": [{
                    "amount": {"currency_code": currency, "value": str(amount)}
                }],
                "application_context": {
                    "return_url": os.getenv("PAYPAL_RETURN_URL", "http://localhost:8000/payment/paypal/success"),
                    "cancel_url": os.getenv("PAYPAL_CANCEL_URL", "http://localhost:8000/payment/paypal/cancel"),
                }
            }
        )
        response.raise_for_status()
        data = response.json()
        approval_url = next(l["href"] for l in data["links"] if l["rel"] == "approve")
        return {"order_id": data["id"], "approval_url": approval_url}

async def capture_paypal_order(order_id: str) -> dict:
    token = await get_paypal_access_token()
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()


async def verify_paypal_webhook(headers: Dict[str, str], event_body: Dict[str, Any]) -> bool:
    if not PAYPAL_WEBHOOK_ID:
        return False

    transmission_id = headers.get("paypal-transmission-id")
    transmission_time = headers.get("paypal-transmission-time")
    cert_url = headers.get("paypal-cert-url")
    auth_algo = headers.get("paypal-auth-algo")
    transmission_sig = headers.get("paypal-transmission-sig")

    if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig]):
        return False

    token = await get_paypal_access_token()
    payload = {
        "transmission_id": transmission_id,
        "transmission_time": transmission_time,
        "cert_url": cert_url,
        "auth_algo": auth_algo,
        "transmission_sig": transmission_sig,
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": event_body,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        verification = response.json()
        return verification.get("verification_status") == "SUCCESS"