"""Cloudflare Turnstile ("I'm not a robot") server-side verification.

The frontend renders a Turnstile widget on the registration form; on submit it
sends the resulting token to /auth/register. We must verify that token
server-side with Cloudflare — the frontend check alone is trivially bypassed by
a bot that posts straight to the API.

Rollout is fail-open-when-unconfigured: if TURNSTILE_SECRET_KEY is not set the
check is skipped entirely, so the site keeps working before the real key is in
place. Setting the secret turns enforcement on with no code change.
"""
import os
import logging

import requests

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def turnstile_enabled() -> bool:
    return bool(os.getenv("TURNSTILE_SECRET_KEY", "").strip())


def verify_turnstile(token: str | None, remote_ip: str | None = None) -> bool:
    """Return True if the human check passed (or if Turnstile is not
    configured). Returns False for a missing/invalid token when enforcement is
    on. Fails closed on a bad token, but treats a Cloudflare outage/timeout as a
    pass so a provider hiccup can't lock every real user out of signup."""
    secret = os.getenv("TURNSTILE_SECRET_KEY", "").strip()
    if not secret:
        return True  # not configured → skip

    if not token:
        return False

    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        resp = requests.post(VERIFY_URL, data=data, timeout=5)
        result = resp.json()
    except Exception as exc:  # network error / timeout / bad JSON
        logger.warning("Turnstile verify call failed, allowing through: %s", exc)
        return True  # fail-open on provider error, not on a bad token

    if not result.get("success"):
        logger.info("Turnstile rejected: %s", result.get("error-codes"))
    return bool(result.get("success"))
