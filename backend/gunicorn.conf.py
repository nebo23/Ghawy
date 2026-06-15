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

# 2 workers for KVM 2 (2 vCPU) — leaves headroom for Nginx & Postgres
workers = 2

# Each worker can handle many concurrent connections via async
worker_connections = 1000

# ── Timeouts ───────────────────────────────────────────────────
timeout = 120          # Allow slow DB queries / file uploads up to 2 min
keepalive = 5          # Reuse connections for 5 seconds
graceful_timeout = 30  # Grace period for in-flight requests on shutdown

# ── Process Management ─────────────────────────────────────────
max_requests = 1000          # Restart worker after N requests (prevents memory leaks)
max_requests_jitter = 100    # Randomize restart to avoid thundering herd
preload_app = True           # Load app before forking — shares memory between workers

# ── Logging ────────────────────────────────────────────────────
accesslog = "-"   # stdout → Docker captures it
errorlog = "-"    # stderr → Docker captures it
loglevel = "warning"
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sus'

# ── Process Naming ─────────────────────────────────────────────
proc_name = "ghawy-api"
