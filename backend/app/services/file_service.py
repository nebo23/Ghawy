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

# Upload categories nginx serves publicly off disk. Anything not listed here is
# delivered by app.routers.files behind an entitlement check, so its stored URL
# must point at /files/ rather than /uploads/.
PUBLIC_UPLOAD_SUBFOLDERS = {"avatars", "course-thumbnails", "posts"}

# Max file sizes
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10 MB
MAX_FILE_SIZE = 25 * 1024 * 1024    # 25 MB
MAX_VOICE_SIZE = 5 * 1024 * 1024    # 5 MB

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VOICE_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav"}

# Extensions a browser will execute on our own origin if it is ever allowed to
# render the file: script, markup and server-side page types. A stored upload
# never gets one of these.
#
# The stored name used to end in `Path(file.filename).suffix` — the attacker's
# own string. A member could upload evil.html as "image/png" and land an
# executable page under ghawy.ai, same-origin with the auth token in
# localStorage, with a chat to spread the link through. nginx already refuses
# to render these (Content-Disposition: attachment, see nginx.conf), but that
# is containment layered on top of the hole rather than the hole being shut:
# it holds only as long as that map keeps listing every dangerous extension,
# and only for files served through nginx.
DANGEROUS_EXTENSIONS = {
    ".html", ".htm", ".xhtml", ".shtml", ".xml", ".svg", ".svgz",
    ".js", ".mjs", ".css", ".php", ".php3", ".php4", ".php5", ".phtml",
    ".phar", ".sh", ".bash", ".py", ".pl", ".cgi", ".jsp", ".asp", ".aspx",
    ".htaccess", ".exe", ".bat", ".cmd", ".com", ".scr", ".jar", ".vbs",
}

# What each accepted media type is actually stored as. The type is validated by
# the caller (chat/avatar uploads both check it against the sets above), so this
# is the extension the file gets — not whatever the filename claimed.
CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
}


def safe_extension(filename: str | None, content_type: str) -> str:
    """The extension an upload is stored under.

    Images and voice notes take theirs from the validated content type. Other
    attachments (the "file" bucket — PDFs, zips, docs) keep the one from their
    name, because that is the only signal we have about what they are, but any
    extension a browser would execute is replaced with an inert one.
    """
    mapped = CONTENT_TYPE_EXTENSIONS.get(content_type)
    if mapped:
        return mapped

    ext = Path(filename or "file").suffix.lower()
    if not ext or len(ext) > 10 or "/" in ext or "\\" in ext:
        return ".bin"
    if ext in DANGEROUS_EXTENSIONS:
        return ".txt"
    return ext

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

    # Generate unique filename. The extension comes from the validated content
    # type where there is one, never straight off the client's filename.
    ext = safe_extension(file.filename, content_type)

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

    # Public categories are served straight off disk by nginx under /uploads/.
    # Everything else (chat and DM attachments, feedback screenshots) is member
    # content and goes through /files/, which checks who is asking.
    prefix = "/uploads" if subfolder in PUBLIC_UPLOAD_SUBFOLDERS else "/files"
    relative_url = f"{prefix}/{subfolder}/{unique_name}"

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
