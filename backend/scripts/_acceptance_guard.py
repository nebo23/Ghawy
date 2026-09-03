"""Refuse to let a destructive acceptance script touch a real database.

Every script in this directory begins by running

    DROP SCHEMA public CASCADE; CREATE SCHEMA public;

against whatever ``DATABASE_URL`` resolves to. That is fine against a scratch
database and catastrophic against any other one, so nothing here runs until
``require_scratch_database()`` has approved the target.

Why the check is on the database NAME and not on the host: on this deployment
the production database is published on 127.0.0.1:5432
(docker-compose.prod.yml), and inside the compose network it answers to the
host ``postgres``. "localhost" therefore proves nothing at all here — the one
signal that actually separates a throwaway database from the real one is that
somebody deliberately named it as a throwaway.
"""
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Keep `import main` and `from app...` working no matter which directory the
# script was launched from.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# A name is only accepted when it announces itself as disposable.
SCRATCH_NAME = re.compile(r"(?i)(^|[_-])(test|tests|scratch|tmp|temp|throwaway)([_-]|\d*$)")

OVERRIDE_VAR = "ACCEPTANCE_DESTROY_DB"


def _resolve_database_url() -> str:
    """Resolve DATABASE_URL exactly the way app.database does.

    app.database anchors dotenv at backend/.env, so the environment alone is not
    the whole story — a .env file can supply a URL the caller never typed.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    try:
        from dotenv import dotenv_values
        return (dotenv_values(BACKEND_DIR / ".env") or {}).get("DATABASE_URL") or ""
    except Exception:
        return ""


def _mask(url: str) -> str:
    return re.sub(r"://([^:/@]*):([^@]*)@", r"://\1:****@", url)


def _production_names() -> set:
    """Database names configured for production, read straight off disk.

    Belt and braces: even a scratch-shaped name is refused if it is the name
    this deployment actually runs on.
    """
    names = set()
    candidates = [
        BACKEND_DIR / ".env.production",
        BACKEND_DIR.parent / ".env",
    ]
    for path in candidates:
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        for match in re.finditer(r"^\s*POSTGRES_DB\s*=\s*(\S+)", text, re.M):
            names.add(match.group(1).strip().strip("'\""))
        for match in re.finditer(r"^\s*DATABASE_URL\s*=\s*(\S+)", text, re.M):
            name = urlparse(match.group(1).strip().strip("'\"")).path.lstrip("/")
            if name:
                names.add(name)
    return {n for n in names if n and not n.startswith("<")}


def _die(reason: str, url: str, dbname: str) -> None:
    print("=" * 72, file=sys.stderr)
    print("REFUSING TO RUN — this script destroys the schema it points at.", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    print(f"  reason        : {reason}", file=sys.stderr)
    print(f"  DATABASE_URL  : {_mask(url) if url else '<unset>'}", file=sys.stderr)
    print(f"  database name : {dbname or '<none>'}", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Point DATABASE_URL at a database whose name says it is disposable,", file=sys.stderr)
    print("  e.g. .../ghawy_test or .../scratch_db, then run again:", file=sys.stderr)
    print("", file=sys.stderr)
    print("      DATABASE_URL=postgresql://user:pw@host:5432/ghawy_test \\", file=sys.stderr)
    print(f"          python {Path(sys.argv[0]).name}", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"  To force a differently-named database, set {OVERRIDE_VAR} to that", file=sys.stderr)
    print("  exact database name. Production names are refused even then.", file=sys.stderr)
    sys.exit(2)


def require_scratch_database() -> str:
    """Approve the target database or exit(2). Returns the resolved db name."""
    url = _resolve_database_url()
    if not url:
        _die("DATABASE_URL is not set and backend/.env supplies none", url, "")

    dbname = urlparse(url).path.lstrip("/")
    if not dbname:
        _die("DATABASE_URL names no database", url, dbname)

    if dbname in _production_names():
        _die("this is the database name configured for production", url, dbname)

    override = os.getenv(OVERRIDE_VAR, "").strip()
    if override:
        if override != dbname:
            _die(f"{OVERRIDE_VAR}={override!r} does not match the target database", url, dbname)
    elif not SCRATCH_NAME.search(dbname):
        _die("the database name does not identify it as a throwaway", url, dbname)

    # Print the target so the operator can see what is about to be dropped.
    print("-" * 72)
    print("destructive acceptance script — target approved by _acceptance_guard")
    print(f"  DATABASE_URL : {_mask(url)}")
    print(f"  dropping schema 'public' in database: {dbname}")
    print("-" * 72)
    return dbname
