"""
Cloudflare R2 service — presigned upload URLs for PDF storage.
Uses boto3 with S3-compatible endpoint.
"""
import os
import logging
import uuid
import boto3
from botocore.config import Config
from pathlib import Path
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "")  # e.g. https://pub-xxx.r2.dev

R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


def _get_client():
    """Create a boto3 S3 client configured for Cloudflare R2."""
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def generate_presigned_upload_url(
    filename: str,
    content_type: str = "application/pdf",
    folder: str = "lesson-pdfs",
    expires_in: int = 600,
) -> dict:
    """
    Generate a presigned PUT URL for uploading a file to R2.
    Returns {"upload_url": str, "public_url": str, "key": str}
    """
    ext = os.path.splitext(filename)[1] or ".pdf"
    key = f"{folder}/{uuid.uuid4().hex}{ext}"

    client = _get_client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": R2_BUCKET_NAME,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
    )

    public_url = f"{R2_PUBLIC_URL}/{key}" if R2_PUBLIC_URL else key

    return {
        "upload_url": upload_url,
        "public_url": public_url,
        "key": key,
    }


def delete_object(key: str) -> bool:
    """Delete an object from R2. Returns True on success."""
    if not key:
        return True
    try:
        client = _get_client()
        client.delete_object(Bucket=R2_BUCKET_NAME, Key=key)
        return True
    except Exception as exc:
        logger.warning("Failed to delete R2 object %s: %s", key, exc)
        return False
