"""Public site statistics — the only endpoint on the API that anonymous
visitors hit on page load.

The landing page (and the standalone marketing pages) show a live member
count. `total_members` already existed inside /admin/analytics/kpis, but that
is admin-only and returns revenue and churn alongside it — nothing there can
be exposed publicly. Hence this separate endpoint, which returns the single
number and nothing else.

Cost control is the whole design here. This is an uncached, public GET fired
by every visitor, and the 2026-07-21 outage showed exactly how that ends when
a sync DB query sits on the request path: sync handlers queue for anyio
threads while holding open transactions, and the pool collapses (see the
comments in app/services/turnstile.py and app/routers/users.py). So:

  * the handler is `async` — a cache hit never occupies a threadpool worker
    and never checks a session out of the pool;
  * the count is recomputed at most once every 5 minutes, off the event loop;
  * only ONE request refreshes at a time — everyone else keeps getting the
    stale value instead of piling onto the DB the moment the TTL expires.

Gunicorn recycles workers roughly every 8 minutes (max_requests), so each
worker computes this a handful of times per lifetime at most.
"""

import threading
import time

from fastapi import APIRouter
from sqlalchemy import func
from starlette.concurrency import run_in_threadpool

from app.database import SessionLocal
from app.models import User

router = APIRouter(prefix="/stats", tags=["Stats"])

CACHE_TTL_SECONDS = 300  # 5 minutes

_lock = threading.Lock()
_total_members = None      # last computed value (None until the first refresh)
_computed_at = 0.0         # time.monotonic() of that computation
_refreshing = False        # a refresh is already in flight


def _count_members() -> int:
    """Runs in a worker thread. Own session, closed immediately — no session
    is ever held across an await."""
    db = SessionLocal()
    try:
        return int(db.query(func.count(User.id)).scalar() or 0)
    finally:
        db.close()


@router.get("/public")
async def public_stats():
    """Public, unauthenticated. Returns the member count and nothing else."""
    global _total_members, _computed_at, _refreshing

    with _lock:
        cached = _total_members
        fresh = cached is not None and (time.monotonic() - _computed_at) < CACHE_TTL_SECONDS
        # Claim the refresh only if the value is stale and nobody else is on it.
        should_refresh = not fresh and not _refreshing
        if should_refresh:
            _refreshing = True

    if not should_refresh:
        # Either the cache is fresh, or another request is already refreshing
        # it — serve what we have. `cached` is None only on the very first
        # concurrent burst after boot; the frontend falls back on its own.
        return {"total_members": cached if cached is not None else 0}

    try:
        total = await run_in_threadpool(_count_members)
    except Exception:
        # Never fail the landing page over a stat. Serve the stale value if we
        # have one, otherwise 0 — the frontend has its own fallback.
        with _lock:
            _refreshing = False
        return {"total_members": cached if cached is not None else 0}

    with _lock:
        _total_members = total
        _computed_at = time.monotonic()
        _refreshing = False

    return {"total_members": total}
