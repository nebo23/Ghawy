"""STAGED, NOT RUN — removes the five fabricated "Guest of Honor" rows from a database.

Why this exists
---------------
`seed_defaults()` inserted five real, named public figures — Sam Altman, Sundar
Pichai, Lex Fridman, Fei-Fei Li and Mark Zuckerberg — as Guests of Honor, each
with an invented rating, an invented attendance figure, and a fabricated
"upcoming" live session. Phase 2 removed that code. Code alone does not remove
rows that are already in the production database and are being served, without
authentication, to anyone who asks for `/api/guests/`.

Before Phase 2 the rows were also self-healing: the guard was
`if db.query(Guest).count() == 0`, so deleting them by hand put them back on the
next restart. **Deploy the Phase 2 backend first, then run this.** Run it against
the old code and the rows return.

What it removes
---------------
Exactly 5 `guests` rows and the 5 `guest_sessions` rows that hang off them
(`ON DELETE CASCADE`, but they are deleted explicitly so the count is reported).
Nothing else in the schema references either table.

Safety
------
* Dry run by default. `--apply` is required to delete anything.
* Every row must match the seeded fingerprint — name, title, company,
  sessions_count, attendees_count and rating all exactly as `seed_defaults()`
  wrote them. A row that differs has been edited by a real admin since, and the
  script **aborts without deleting anything** rather than guess.
* A row with an `avatar_url`, or a session with a `platform`/`session_url`, or
  any session whose `attendees_count`/`rating` is non-zero, counts as edited.
* Everything it is about to delete is written to a timestamped JSON backup
  first, so the deletion is reversible. Writability is proved *before* the
  DELETE, not after — the image runs as a non-root user and cannot write inside
  /app, and discovering that after the delete would mean rows gone and no
  backup.

Usage
-----
    python scripts/cleanup_seeded_public_figures.py --backup-dir /tmp
    python scripts/cleanup_seeded_public_figures.py --backup-dir /tmp --apply

In the production container, /app is not writable — pass a `--backup-dir` on a
mounted volume (for example `/app/uploads`) or copy the backup out afterwards.
"""

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, DATABASE_URL  # noqa: E402

# Exactly as seed_defaults() wrote them. Any deviation means a human touched the
# row, and this script will not delete a row a human has touched.
FINGERPRINT = {
    "Sam Altman":      ("CEO of OpenAI", "OpenAI",   12, 15000, 4.9),
    "Sundar Pichai":   ("CEO of Google", "Google",    8, 12000, 4.8),
    "Lex Fridman":     ("AI Researcher", "MIT",       6,  8000, 4.9),
    "Fei-Fei Li":      ("AI Pioneer",    "Stanford",  5,  6000, 4.8),
    "Mark Zuckerberg": ("CEO of Meta",   "Meta",      4, 10000, 4.7),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default is a dry run)")
    ap.add_argument("--backup-dir", default=os.getcwd(),
                    help="where to write the JSON backup (default: current directory). "
                         "The container runs as a non-root user and cannot write inside /app.")
    args = ap.parse_args()

    safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    print(f"database: ...@{safe_url}")
    print(f"mode:     {'APPLY (rows will be deleted)' if args.apply else 'DRY RUN (nothing will be deleted)'}\n")

    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id, name, title, company, sessions_count, attendees_count, rating, avatar_url, bio, category, is_featured "
            "FROM guests WHERE name = ANY(:names) ORDER BY id"
        ), {"names": list(FINGERPRINT)}).mappings().all()

        if not rows:
            print("Nothing to do — none of the five names is present.")
            return 0

        problems = []
        for r in rows:
            want = FINGERPRINT[r["name"]]
            got = (r["title"], r["company"], r["sessions_count"], r["attendees_count"], float(r["rating"] or 0))
            if got != want:
                problems.append(f"  guests.id={r['id']} {r['name']}: expected {want}, found {got}")
            if r["avatar_url"]:
                problems.append(f"  guests.id={r['id']} {r['name']}: has an uploaded avatar ({r['avatar_url']})")

        guest_ids = [r["id"] for r in rows]
        sessions = db.execute(text(
            "SELECT id, guest_id, title, description, session_date, platform, session_url, status, attendees_count, rating "
            "FROM guest_sessions WHERE guest_id = ANY(:ids) ORDER BY id"
        ), {"ids": guest_ids}).mappings().all()

        for s in sessions:
            if s["platform"] or s["session_url"]:
                problems.append(f"  guest_sessions.id={s['id']}: has a real platform/url — someone scheduled this")
            if (s["attendees_count"] or 0) or float(s["rating"] or 0):
                problems.append(f"  guest_sessions.id={s['id']}: has attendees or a rating — someone ran this session")

        print(f"guests to remove:         {len(rows)}  (ids {guest_ids})")
        for r in rows:
            print(f"    id={r['id']:<4} {r['name']:<16} {r['title']:<14} rating={r['rating']} attendees={r['attendees_count']}")
        print(f"guest_sessions to remove: {len(sessions)}  (ids {[s['id'] for s in sessions]})")
        for s in sessions:
            print(f"    id={s['id']:<4} {s['title']}  ({s['status']}, {s['session_date']})")

        if problems:
            print("\nABORT — these rows are not what seed_defaults() wrote, so a human has")
            print("edited them since. Review each one by hand; this script will not guess.\n")
            print("\n".join(problems))
            return 2

        print("\nAll rows match the seeded fingerprint exactly — none has been edited.")

        # Prove the backup can be written *before* deleting anything. The image
        # runs as a non-root user, so /app is read-only to it — finding that out
        # after the DELETE would mean rows gone and no backup.
        stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        backup = os.path.join(args.backup_dir, f"removed_seeded_guests_{stamp}.json")
        try:
            with open(backup, "w", encoding="utf-8") as fh:
                fh.write("")
        except OSError as e:
            print(f"\nABORT — cannot write the backup to {backup}: {e}")
            print("Pass --backup-dir <a writable directory>. Nothing was deleted.")
            return 4

        if not args.apply:
            os.remove(backup)
            print(f"\nDry run. Backup location is writable ({args.backup_dir}).")
            print("Re-run with --apply to delete.")
            return 0

        with open(backup, "w", encoding="utf-8") as fh:
            json.dump({
                "removed_at": stamp,
                "guests": [dict(r) for r in rows],
                "guest_sessions": [dict(s) for s in sessions],
            }, fh, indent=2, ensure_ascii=False, default=str)
        print(f"\nbackup written: {backup}")

        n_sessions = db.execute(text("DELETE FROM guest_sessions WHERE guest_id = ANY(:ids)"),
                                {"ids": guest_ids}).rowcount
        n_guests = db.execute(text("DELETE FROM guests WHERE id = ANY(:ids)"),
                              {"ids": guest_ids}).rowcount
        db.commit()
        print(f"deleted: {n_guests} guests, {n_sessions} guest_sessions")

        left = db.execute(text("SELECT count(*) FROM guests WHERE name = ANY(:names)"),
                          {"names": list(FINGERPRINT)}).scalar()
        print(f"verification — rows with those five names remaining: {left}")
        return 0 if left == 0 else 3
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
