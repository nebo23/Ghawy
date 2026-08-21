import os
import json
import requests
import logging

logger = logging.getLogger(__name__)

VDOCIPHER_API_URL = "https://dev.vdocipher.com/api"


def generate_otp(video_id: str, user_id: int = None, user_name: str = None) -> dict:
    """
    Generate an OTP + playbackInfo for a VdoCipher video.
    Returns dict with 'otp' and 'playbackInfo' keys.
    Raises ValueError if the API call fails.

    VdoCipher 'annotate' field must be a JSON-encoded STRING (not a dict/list directly).
    Format: json.dumps([{annotation_object}, ...])
    """
    api_key = os.environ.get("VDOCIPHER_API_KEY")
    if not api_key:
        raise ValueError("VDOCIPHER_API_KEY not set in environment")

    url = f"{VDOCIPHER_API_URL}/videos/{video_id}/otp"
    headers = {
        "Authorization": f"Apisecret {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # How long the OTP stays usable, in seconds. The request used to carry no
    # ttl at all, so a captured OTP was good for VdoCipher's default window —
    # long enough to hand around. Five minutes is ample to start playback, and
    # playback itself continues after the OTP is spent.
    ttl = int(os.environ.get("VDOCIPHER_OTP_TTL", "300"))

    # Build watermark annotation
    # VdoCipher expects `annotate` as a JSON-encoded STRING of an array of annotation objects
    payload: dict = {"ttl": ttl}
    if user_id or user_name:
        parts = []
        if user_name:
            parts.append(user_name)
        if user_id:
            parts.append(f"ID: {user_id}")
        watermark_text = "  |  ".join(parts)

        annotation_obj = {
            "type": "rtext",
            "text": watermark_text,
            "alpha": "0.60",
            "color": "FF0000",
            "size": "15",
            "interval": "5000",
        }
        # IMPORTANT: annotate must be a stringified JSON array
        payload["annotate"] = json.dumps([annotation_obj])

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code in (200, 201):
            data = response.json()
            return {"otp": data["otp"], "playbackInfo": data["playbackInfo"]}
        else:
            logger.error(
                f"VdoCipher OTP generation failed for video {video_id}. "
                f"Status: {response.status_code}, Body: {response.text}"
            )
            raise ValueError(f"VdoCipher API error: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.error(f"VdoCipher request error: {e}")
        raise ValueError(f"VdoCipher request failed: {e}")
