import os
import uuid
import io
import asyncio
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

# Image compression targets — keeps the web fast without noticeable quality loss.
# Avatars render tiny (≤120px), so a small max dimension is plenty.
AVATAR_MAX_DIM = 400
IMAGE_MAX_DIM = 1600
IMAGE_QUALITY = 82


def compress_image_bytes(content: bytes, ext: str, max_dim: int, quality: int = IMAGE_QUALITY) -> tuple[bytes, str]:
    """
    Resize (down only) and re-encode an image to shrink its byte size.
    Returns (new_bytes, new_ext). Falls back to the original bytes/ext on any
    problem or if compression wouldn't actually help. Animated GIFs are left
    untouched so their animation is preserved.
    """
    e = ext.lower().lstrip(".")
    if e == "gif":
        return content, ext  # keep animated GIFs as-is

    try:
        from PIL import Image, ImageOps
    except Exception:
        return content, ext  # Pillow not available — serve original

    try:
        img = Image.open(io.BytesIO(content))
        img = ImageOps.exif_transpose(img)  # honour camera orientation

        # Downscale only (never upscale)
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)

        out = io.BytesIO()
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)

        if e in ("jpg", "jpeg"):
            img.convert("RGB").save(out, "JPEG", quality=quality, optimize=True, progressive=True)
            new_ext = ".jpg"
        elif e == "webp":
            img.save(out, "WEBP", quality=quality, method=6)
            new_ext = ".webp"
        elif e == "png":
            if has_alpha:
                img.save(out, "PNG", optimize=True)
                new_ext = ".png"
            else:
                # No transparency → JPEG is far smaller than PNG
                img.convert("RGB").save(out, "JPEG", quality=quality, optimize=True, progressive=True)
                new_ext = ".jpg"
        else:
            return content, ext

        data = out.getvalue()
        # Only use the compressed version if it's actually smaller
        if data and len(data) < len(content):
            return data, new_ext
        return content, ext
    except Exception:
        return content, ext  # corrupt/unsupported — serve original


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

    # Compress images so they load fast for everyone.
    # Runs in a worker thread — compression is CPU-bound and would otherwise
    # block the single async event loop and stall every other request/WS.
    if message_type == "image":
        max_dim = AVATAR_MAX_DIM if subfolder == "avatars" else IMAGE_MAX_DIM
        content, ext = await asyncio.to_thread(compress_image_bytes, content, ext, max_dim)
        file_size = len(content)

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
