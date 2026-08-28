#!/usr/bin/env python3
"""Rewrite stored upload URLs from /uploads/<cat>/ to /files/<cat>/.

The protected upload categories moved from "served off disk by nginx" to
"served by app.routers.files behind an entitlement check", which changed the URL
prefix. Rows written before the move still point at /uploads/, where nginx no
longer answers — this walks every column that stores such a URL and rewrites it.

Only the protected categories are touched. avatars, course-thumbnails and posts
are still public and still live under /uploads/.

Idempotent: a URL already on /files/ is left alone, so re-running is a no-op.

Run inside the backend container (the image has no scripts/ dir, so copy it in):
    docker cp scripts/migrate_upload_urls.py ghawy_backend:/tmp/
    docker exec ghawy_backend python /tmp/migrate_upload_urls.py --dry-run
or, from the repo root with DATABASE_URL set:
    python scripts/migrate_upload_urls.py --dry-run
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import Text, cast

# The repo layout puts the app under backend/; the container puts it at /app and
# the script gets copied to /tmp, so the repo-relative guess misses entirely.
# Offer both and let the import pick whichever exists.
for candidate in (Path(__file__).resolve().parents[1] / "backend", Path("/app")):
    if (candidate / "app").is_dir():
        sys.path.insert(0, str(candidate))
        break

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Course, Lesson, Message, ProjectSubmission, ManualPaymentRequest,
    CommunityFeedback, AiUpdatePost,
)

PROTECTED = (
    "lesson-pdfs", "course-pdfs", "course-certificates",
    "receipts", "projects", "chat", "feedbacks",
)

# (model, attribute) for every column that stores an upload URL. lesson.pdf_url
# and course.pdf_url hold a JSON array rather than a bare URL, which is exactly
# why this rewrites by substring instead of parsing: one rule covers both shapes.
TARGETS = [
    (Lesson, "pdf_url"),
    (Course, "pdf_url"),
    (Course, "certificate_url"),
    (ManualPaymentRequest, "receipt_url"),
    (ProjectSubmission, "file_url"),
    (Message, "file_url"),
    (CommunityFeedback, "image_url"),
    # AI Updates posts upload through /chat/upload, so their images land in the
    # (protected) chat category and moved with it. Missing from the first pass,
    # which is why every image in the feed 404'd.
    (AiUpdatePost, "image_url"),
]

# Same rewrite, but these columns are real JSON (a list of {"type", "url"})
# rather than a URL string, so the value has to be walked instead of replaced —
# and the SQL narrowing has to compare as text, because `contains` on a JSON
# column is containment (@>), not substring.
JSON_TARGETS = [
    (AiUpdatePost, "media"),
]


def rewrite(value: str) -> str:
    for category in PROTECTED:
        value = value.replace(f"/uploads/{category}/", f"/files/{category}/")
    return value


def rewrite_json(value):
    """Rewrite every "url" string inside a decoded JSON value, in place-ish.

    Returns a new value; the caller compares it against the original to decide
    whether the row changed. Anything that is not a str/list/dict comes back
    untouched.
    """
    if isinstance(value, str):
        return rewrite(value)
    if isinstance(value, list):
        return [rewrite_json(v) for v in value]
    if isinstance(value, dict):
        return {k: rewrite_json(v) for k, v in value.items()}
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without writing")
    args = parser.parse_args()

    db = SessionLocal()
    total = 0
    try:
        for model, attr in TARGETS:
            column = getattr(model, attr)
            # Narrow in SQL first — Message alone has thousands of rows and only
            # the ones carrying an attachment are candidates.
            rows = db.query(model).filter(column.contains("/uploads/")).all()
            changed = 0
            for row in rows:
                current = getattr(row, attr)
                if not current:
                    continue
                updated = rewrite(current)
                if updated != current:
                    if not args.dry_run:
                        setattr(row, attr, updated)
                    changed += 1
            total += changed
            print(f"{model.__tablename__}.{attr}: {changed} row(s)"
                  + (" would change" if args.dry_run else " updated"))

        for model, attr in JSON_TARGETS:
            column = getattr(model, attr)
            rows = db.query(model).filter(
                cast(column, Text).contains("/uploads/")
            ).all()
            changed = 0
            for row in rows:
                current = getattr(row, attr)
                if not current:
                    continue
                updated = rewrite_json(current)
                if updated != current:
                    if not args.dry_run:
                        # A JSON column mutated in place is not seen as dirty —
                        # assigning a fresh object is what flags it for UPDATE.
                        setattr(row, attr, updated)
                    changed += 1
            total += changed
            print(f"{model.__tablename__}.{attr}: {changed} row(s)"
                  + (" would change" if args.dry_run else " updated"))

        if args.dry_run:
            db.rollback()
            print(f"\nDRY RUN — {total} row(s) would change. Nothing written.")
        else:
            db.commit()
            print(f"\n{total} row(s) updated.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
