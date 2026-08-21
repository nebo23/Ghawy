#!/usr/bin/env python3
"""Rewrite stored upload URLs from /uploads/<cat>/ to /files/<cat>/.

The protected upload categories moved from "served off disk by nginx" to
"served by app.routers.files behind an entitlement check", which changed the URL
prefix. Rows written before the move still point at /uploads/, where nginx no
longer answers — this walks every column that stores such a URL and rewrites it.

Only the protected categories are touched. avatars, course-thumbnails and posts
are still public and still live under /uploads/.

Idempotent: a URL already on /files/ is left alone, so re-running is a no-op.

Run inside the backend container:
    docker compose -f docker-compose.prod.yml exec backend \\
        python /app/../scripts/migrate_upload_urls.py [--dry-run]
or, from the repo root with DATABASE_URL set:
    python scripts/migrate_upload_urls.py --dry-run
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Course, Lesson, Message, ProjectSubmission, ManualPaymentRequest,
    CommunityFeedback,
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
]


def rewrite(value: str) -> str:
    for category in PROTECTED:
        value = value.replace(f"/uploads/{category}/", f"/files/{category}/")
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
