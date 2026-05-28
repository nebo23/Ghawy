"""
Cloudflare Stream service — direct upload, status polling, deletion.
"""
import os
import logging
import requests
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)

CF_ACCOUNT_ID = os.getenv("CF_ACCOUNT_ID", "")
CF_API_TOKEN = os.getenv("CF_API_TOKEN", "")
CF_BASE = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/stream"


def _headers():
    return {"Authorization": f"Bearer {CF_API_TOKEN}"}


def create_direct_upload(max_duration_seconds: int = 3600) -> dict:
    """
    Create a one-time direct upload URL via Cloudflare Stream TUS protocol.
    Returns {"upload_url": str, "video_id": str}
    """
    url = f"{CF_BASE}/direct_upload"
    payload = {"maxDurationSeconds": max_duration_seconds}

    resp = requests.post(url, headers=_headers(), json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    result = data.get("result", {})
    return {
        "upload_url": result.get("uploadURL", ""),
        "video_id": result.get("uid", ""),
    }


def get_video_status(video_id: str) -> str:
    """
    Poll Cloudflare Stream for video processing status.
    Returns "processing", "ready", or "error".
    """
    url = f"{CF_BASE}/{video_id}"
    resp = requests.get(url, headers=_headers(), timeout=10)

    if resp.status_code == 404:
        return "error"

    resp.raise_for_status()
    data = resp.json()
    result = data.get("result", {})

    if result.get("readyToStream"):
        return "ready"

    status_info = result.get("status", {})
    state = status_info.get("state", "processing")

    if state in ("error", "inprogress"):
        return "error" if state == "error" else "processing"

    return "processing"


def get_video_details(video_id: str) -> dict:
    """Get full video details from Cloudflare Stream."""
    url = f"{CF_BASE}/{video_id}"
    resp = requests.get(url, headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json().get("result", {})


def get_embed_url(video_id: str) -> str:
    """Return the iframe-embeddable URL for a video."""
    return f"https://customer-{CF_ACCOUNT_ID}.cloudflarestream.com/{video_id}/iframe"


def get_playback_url(video_id: str) -> str:
    """Return the HLS playback URL."""
    return f"https://customer-{CF_ACCOUNT_ID}.cloudflarestream.com/{video_id}/manifest/video.m3u8"


def delete_video(video_id: str) -> bool:
    """Delete a video from Cloudflare Stream. Returns True on success."""
    if not video_id:
        return True
    url = f"{CF_BASE}/{video_id}"
    try:
        resp = requests.delete(url, headers=_headers(), timeout=10)
        return resp.status_code in (200, 204, 404)
    except Exception as exc:
        logger.warning("Failed to delete CF video %s: %s", video_id, exc)
        return False
