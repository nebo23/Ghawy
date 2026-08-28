"""Authorized delivery of protected uploads.

Every file under `uploads/` used to be served straight off disk by nginx and by
a StaticFiles mount, with `Cache-Control: public` and no authorization at all.
Course PDFs, payment receipts, project submissions and chat/DM attachments were
world-readable to anyone who knew — or guessed — a filename. That is how the
whole course library walked out of the door.

Files now split by sensitivity:

  public     avatars, course-thumbnails, posts — still served by nginx, because
             they are content the marketing site renders to strangers anyway.
  protected  everything else — served only from here, only to a caller who is
             entitled to that specific file, and never cached by a shared proxy.

"Entitled to that specific file" is the important half. Being an active member
is not enough to read a receipt, and having any chat account is not enough to
read an attachment from a DM you are not in: each category resolves the file
back to the row that owns it and asks the same question the rest of the app
asks about that row.
"""

import mimetypes
import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, Cookie
from fastapi.responses import FileResponse
from jose import jwt, JWTError
from sqlalchemy import Text, cast, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    User, Course, Lesson, Message, ProjectSubmission, ManualPaymentRequest,
    CommunityFeedback, AiUpdatePost,
)
from app.routers.users import (
    SECRET_KEY, ALGORITHM, FILE_TOKEN_COOKIE, set_file_cookie,
    get_current_user, optional_oauth2_scheme,
)

router = APIRouter(prefix="/files", tags=["Files"])

UPLOADS_DIR = (Path(__file__).resolve().parents[2] / "uploads").resolve()

# Served by nginx off disk — no token, no backend hop. Listed here so the
# category check can reject them explicitly rather than serving them twice.
PUBLIC_CATEGORIES = {"avatars", "course-thumbnails", "posts"}

PROTECTED_CATEGORIES = {
    "lesson-pdfs", "course-pdfs", "course-certificates",
    "receipts", "projects", "chat", "feedbacks",
}

# Types the browser may render in place. A protected upload is delivered inline
# only when it is one of these; anything else downloads, so an unexpected file
# type can never execute on our own origin.
INLINE_TYPES = {
    "application/pdf",
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "audio/webm", "audio/ogg", "audio/mpeg", "audio/mp4", "audio/wav",
    "video/mp4", "video/webm",
}

# Python's mimetypes does not know .m4a or .ogg at all, and calls .wav
# "audio/x-wav" — none of which are in INLINE_TYPES. So a voice note in any of
# those formats was answered as application/octet-stream with
# Content-Disposition: attachment, which is not something an <audio> element
# will play. Safari (i.e. every browser on iOS) records voice notes as m4a, so
# this map is the difference between an iPhone voice note playing and not.
EXTENSION_TYPES = {
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".opus": "audio/ogg",
    ".wav": "audio/wav",
}

# When set, the response carries X-Accel-Redirect and nginx serves the file off
# disk from its `internal` location instead of the bytes crossing Python. Unset
# in local dev (no nginx in front), where FileResponse is used instead.
X_ACCEL_PREFIX = os.getenv("X_ACCEL_UPLOADS_PREFIX", "").strip()

_FORBIDDEN = HTTPException(status_code=403, detail="You are not allowed to open this file")
# 404, not 403, wherever confirming that the file exists is itself a leak.
_NOT_FOUND = HTTPException(status_code=404, detail="File not found")


# ─── Who is asking ────────────────────────────────────────────

def _user_from_file_cookie(token: Optional[str], db: Session) -> Optional[User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("typ") != "file":
            return None
        user_id = int(payload.get("sub"))
    except (JWTError, ValueError, TypeError):
        return None
    return db.query(User).filter(User.id == user_id).first()


def file_requester(
    bearer: Optional[str] = Depends(optional_oauth2_scheme),
    ghawy_files: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """The member behind a file request, from the bearer header or the cookie.

    Both are accepted because both really happen: JS-driven downloads send the
    header, while <img>, <a href> and <audio src> can only send the cookie.
    """
    if bearer:
        try:
            payload = jwt.decode(bearer, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("typ") != "file":
                user = db.query(User).filter(User.id == int(payload.get("sub"))).first()
                if user:
                    return user
        except (JWTError, ValueError, TypeError):
            pass

    user = _user_from_file_cookie(ghawy_files, db)
    if user:
        return user

    raise HTTPException(
        status_code=401,
        detail="Sign in to open this file",
        headers={"WWW-Authenticate": "Bearer"},
    )


# ─── Locating the file ────────────────────────────────────────

def _resolve(category: str, filename: str) -> Path:
    """The on-disk path for one upload, or 404.

    Built by joining and then re-resolving, and the result must still sit inside
    the uploads tree — a filename is never trusted to stay where it was put.
    """
    if "/" in filename or "\\" in filename or filename in ("", ".", ".."):
        raise _NOT_FOUND

    category_root = (UPLOADS_DIR / category).resolve()
    if not category_root.is_relative_to(UPLOADS_DIR):
        raise _NOT_FOUND

    path = (category_root / filename).resolve()
    if not path.is_relative_to(category_root) or not path.is_file():
        raise _NOT_FOUND
    return path


def _referenced(db: Session, column, filename: str) -> bool:
    """Is this filename actually pointed at by a stored URL in `column`?

    Matched as a substring on "/<filename>" so it works for a bare URL, for the
    JSON arrays that lesson/course PDFs are stored as, and for the `#d=` suffix
    voice notes carry — and so it survives the /uploads/ → /files/ migration in
    either direction.
    """
    return db.query(column).filter(column.contains("/" + filename)).first() is not None


def _referenced_by_ai_update(db: Session, filename: str) -> bool:
    """Is this filename attached to an AI Updates post?

    Two columns to check: image_url holds the first attachment for legacy
    readers, media holds the full list. media is real JSON, so it is compared as
    text — `contains` on a JSON column means containment, not substring.
    """
    needle = "/" + filename
    return db.query(AiUpdatePost.id).filter(
        or_(
            AiUpdatePost.image_url.contains(needle),
            cast(AiUpdatePost.media, Text).contains(needle),
        )
    ).first() is not None


# ─── Per-category entitlement ─────────────────────────────────

def _require_active(user: User) -> None:
    if not user.is_active:
        raise HTTPException(status_code=402, detail="حسابك غير مفعل — يرجى تجديد الاشتراك")


def _is_staff(user: User) -> bool:
    return bool(user.is_admin or getattr(user, "is_owner", False))


def _authorize(db: Session, user: User, category: str, filename: str) -> None:
    if category in ("lesson-pdfs", "course-pdfs", "course-certificates"):
        # Course material: any active member may read it, but only if the file
        # is really course material. Without this check an active member could
        # read a receipt by dropping its name into the lesson-pdfs path.
        _require_active(user)
        column = {
            "lesson-pdfs": Lesson.pdf_url,
            "course-pdfs": Course.pdf_url,
            "course-certificates": Course.certificate_url,
        }[category]
        if not _referenced(db, column, filename):
            raise _NOT_FOUND
        return

    if category == "receipts":
        if _is_staff(user):
            return
        # A manual payment request has no user_id — the payer is identified by
        # the email they typed on the form, so that is what "their own receipt"
        # means here. Compared case-insensitively, since the payer typed it.
        own = db.query(ManualPaymentRequest.id).filter(
            func.lower(ManualPaymentRequest.email) == (user.email or "").lower(),
            ManualPaymentRequest.receipt_url.contains("/" + filename),
        ).first()
        if not own:
            raise _FORBIDDEN
        return

    if category == "projects":
        submission = db.query(ProjectSubmission).filter(
            ProjectSubmission.file_url.contains("/" + filename)
        ).first()
        if not submission:
            raise _NOT_FOUND
        if not (_is_staff(user) or submission.user_id == user.id):
            raise _FORBIDDEN
        return

    if category == "feedbacks":
        if _is_staff(user):
            return
        own = db.query(CommunityFeedback.id).filter(
            CommunityFeedback.user_id == user.id,
            CommunityFeedback.image_url.contains("/" + filename),
        ).first()
        if not own:
            raise _FORBIDDEN
        return

    if category == "chat":
        # AI Updates posts upload through /chat/upload, so their images share
        # this category while belonging to the feed, not to any channel. The
        # feed is readable by any active member, so that is the gate here — the
        # channel check below would reject them outright, since no Message row
        # ever points at these files.
        if _referenced_by_ai_update(db, filename):
            _require_active(user)
            return

        message = db.query(Message).filter(
            Message.file_url.contains("/" + filename)
        ).first()
        if not message:
            raise _NOT_FOUND
        # The one gate the rest of chat uses: it refuses a DM to anyone who is
        # not a participant, and returns 404 rather than confirming it exists.
        from app.routers.chat import ensure_channel_access
        ensure_channel_access(db, message.channel_id, user)
        return

    raise _NOT_FOUND


# ─── The endpoint ─────────────────────────────────────────────

@router.post("/session")
def start_file_session(response: Response, current_user: User = Depends(get_current_user)):
    """Mint the file-access cookie for a session that already holds a JWT.

    Login sets this cookie directly; this exists for the members who were
    already signed in when the cookie was introduced, and for whenever it
    expires before the session does.
    """
    set_file_cookie(response, current_user.id)
    return {"ok": True}


@router.delete("/session")
def end_file_session(response: Response):
    """Drop the file-access cookie. Called by logout, so signing out on a shared
    machine really does close the door on the member's files."""
    response.delete_cookie(FILE_TOKEN_COOKIE, path="/")
    return {"ok": True}


@router.get("/{category}/{filename}")
def get_file(
    category: str,
    filename: str,
    db: Session = Depends(get_db),
    user: User = Depends(file_requester),
):
    if category in PUBLIC_CATEGORIES:
        # These never needed a token; nginx serves them. Answering here too
        # would just be a slower second door onto the same bytes.
        raise _NOT_FOUND
    if category not in PROTECTED_CATEGORIES:
        raise _NOT_FOUND

    path = _resolve(category, filename)
    _authorize(db, user, category, filename)

    media_type = (
        EXTENSION_TYPES.get(path.suffix.lower())
        or mimetypes.guess_type(path.name)[0]
        or "application/octet-stream"
    )
    disposition = "inline" if media_type in INLINE_TYPES else "attachment"
    headers = {
        # Never let a shared cache hold a file that was authorized per-user.
        "Cache-Control": "private, no-store",
        "Content-Disposition": f'{disposition}; filename="{path.name}"',
        "X-Content-Type-Options": "nosniff",
    }

    if X_ACCEL_PREFIX:
        # Authorization happens here; the bytes are handed back to nginx, which
        # serves them off disk from an `internal` location. Chat attachments
        # alone are four figures of files loaded on every chat page — streaming
        # those through a single-worker gunicorn would tie up an anyio thread
        # per download, which is precisely the shape of the July threadpool
        # congestion collapse. This keeps the check without the load.
        headers["X-Accel-Redirect"] = f"{X_ACCEL_PREFIX}{quote(category)}/{quote(path.name)}"
        return Response(status_code=200, headers=headers, media_type=media_type)

    return FileResponse(path, media_type=media_type, headers=headers)
