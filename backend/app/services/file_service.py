import os
import uuid
import aiofiles
from pathlib import Path
from fastapi import UploadFile

BACKEND_DIR = Path(__file__).resolve().parents[2]
UPLOADS_DIR = BACKEND_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

# Max file sizes
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 MB
MAX_FILE_SIZE = 25 * 1024 * 1024    # 25 MB
MAX_VOICE_SIZE = 5 * 1024 * 1024    # 5 MB

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VOICE_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav"}


async def save_upload(file: UploadFile, subfolder: str = "general") -> dict:
    """
    Save an uploaded file and return its metadata.
    Returns: {"file_url": str, "file_name": str, "file_size": int, "message_type": str}
    """
    # Create subfolder
    folder = UPLOADS_DIR / subfolder
    folder.mkdir(exist_ok=True)

    # Determine message type from content type
    content_type = file.content_type or ""
    if content_type in ALLOWED_IMAGE_TYPES:
        message_type = "image"
        max_size = MAX_IMAGE_SIZE
    elif content_type in ALLOWED_VOICE_TYPES:
        message_type = "voice"
        max_size = MAX_VOICE_SIZE
    else:
        message_type = "file"
        max_size = MAX_FILE_SIZE

    # Read file content
    content = await file.read()
    file_size = len(content)

    if file_size > max_size:
        raise ValueError(f"File too large. Max size: {max_size // (1024*1024)} MB")

    # Generate unique filename
    ext = Path(file.filename or "file").suffix or ".bin"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = folder / unique_name

    # Write file
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Return relative URL path (served by StaticFiles mount at /uploads)
    relative_url = f"/uploads/{subfolder}/{unique_name}"

    return {
        "file_url": relative_url,
        "file_name": file.filename or unique_name,
        "file_size": file_size,
        "message_type": message_type,
    }


async def save_avatar(file: UploadFile) -> str:
    """Save avatar image and return its URL path."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("Avatar must be an image (JPEG, PNG, GIF, or WebP)")

    result = await save_upload(file, subfolder="avatars")
    return result["file_url"]
