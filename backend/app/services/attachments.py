"""Deriving a message attachment from what a client claims about it.

The chat socket used to store `file_url`, `file_name` and `file_size` exactly as
the sender wrote them, with nothing tying any of it to an actual upload. Two
things follow from that, and the second is the nastier one:

  * `file_url` is interpolated into src="..." and into a single-quoted
    onclick="openLightbox('...')" when the message renders — an attribute
    break-out and a JS-string break-out on one line, in every recipient's
    browser, with the auth token sitting in localStorage.

  * a sender could name someone else's file. Point a message in a public
    channel at an attachment from a private DM and the file endpoint, asked
    "is there a message with this file that you can see?", would say yes.

So the attachment is resolved here instead of trusted: the URL has to be one
this server could have issued, the file has to exist, and no earlier message may
already claim it — a fresh upload is referenced by nothing. Size comes off disk
rather than from the sender.
"""

import re
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Message

UPLOADS_DIR = (Path(__file__).resolve().parents[2] / "uploads").resolve()

# The shape save_upload() writes: /files/chat/<uuid>.<ext>, optionally carrying
# the #d=<seconds> fragment the voice recorder appends so receivers can show a
# duration without downloading the audio. /uploads/ is still accepted because
# messages predating the move to authorized delivery carry that prefix.
ATTACHMENT_RE = re.compile(
    r"^/(?:uploads|files)/(chat|posts)/([A-Za-z0-9._-]{1,120})(#d=\d+(?:\.\d+)?)?$"
)

MAX_FILE_NAME = 255


class InvalidAttachment(ValueError):
    """The claimed attachment is not one this server issued to this sender."""


def resolve_attachment(
    db: Session,
    file_url: Optional[str],
    file_name: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[int]]:
    """Return the (file_url, file_name, file_size) to store, or raise.

    A message with no attachment resolves to three Nones.
    """
    if not file_url:
        return None, None, None

    match = ATTACHMENT_RE.match(file_url.strip())
    if not match:
        raise InvalidAttachment("file_url is not an upload this server issued")

    category, stored_name, fragment = match.groups()

    path = (UPLOADS_DIR / category / stored_name).resolve()
    if not path.is_relative_to(UPLOADS_DIR) or not path.is_file():
        raise InvalidAttachment("attachment does not exist")

    # A just-uploaded file belongs to nobody yet. If a message already points at
    # it, this sender is claiming someone else's attachment.
    already_claimed = db.query(Message.id).filter(
        Message.file_url.contains("/" + stored_name)
    ).first()
    if already_claimed:
        raise InvalidAttachment("attachment is already attached to another message")

    # Normalize to the authorized-delivery prefix regardless of what was sent,
    # and keep the duration fragment, which is display metadata rather than part
    # of the path (browsers never send a fragment to the server).
    normalized = f"/files/{category}/{stored_name}{fragment or ''}"

    display_name = (file_name or stored_name).replace("<", "").replace(">", "")
    display_name = "".join(ch for ch in display_name if ch.isprintable())[:MAX_FILE_NAME]

    # Off disk, not from the sender: the number is shown to recipients and there
    # is no reason to take the sender's word for it.
    return normalized, display_name or stored_name, path.stat().st_size
