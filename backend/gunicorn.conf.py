"""
Gunicorn configuration for Ghawy production on Hostinger KVM 2
Specs: 2 vCPU, 8 GB RAM

Rule of thumb: workers = (2 × CPU cores) + 1 = 5
But since this is async (uvicorn), 2-3 workers is optimal to avoid memory pressure.
"""
import multiprocessing

# ── Binding ────────────────────────────────────────────────────
bind = "0.0.0.0:8000"
backlog = 2048

# ── Workers ────────────────────────────────────────────────────
# UvicornWorker handles async FastAPI/WebSocket correctly
worker_class = "uvicorn.workers.UvicornWorker"

# ⚠️  MUST be 1 — the WebSocket manager uses an in-memory Singleton.
# With multiple workers each process has its own manager, so reactions
# and broadcasts only reach users connected to that specific worker.
# Async uvicorn handles thousands of concurrent connections in 1 worker.
workers = 1

# Each worker can handle many concurrent connections via async
worker_connections = 1000

# ── Timeouts ───────────────────────────────────────────────────
# NOTE: With uvicorn async workers, timeout=0 means unlimited — worker will not be
# killed for long-running requests/WebSocket connections. Nginx controls WS timeout.
timeout = 0            # Must be 0 for WebSocket (long-lived) connections with UvicornWorker
keepalive = 5          # Reuse connections for 5 seconds
graceful_timeout = 30  # Grace period for in-flight requests on shutdown

# ── Process Management ─────────────────────────────────────────
max_requests = 10000         # Restart worker after N requests (prevents memory leaks)
max_requests_jitter = 1000   # Randomize restart to avoid thundering herd
preload_app = False          # Must be False with WebSocket singleton manager

# ── Logging ────────────────────────────────────────────────────
accesslog = "-"   # stdout → Docker captures it
errorlog = "-"    # stderr → Docker captures it
loglevel = "warning"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sus'

# ── Process Naming ─────────────────────────────────────────────
proc_name = "ghawy-api"
