# ── Stage 1: Builder ───────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies into a prefix dir
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: Runtime ───────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Install runtime-only system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    # WeasyPrint (invoice PDF): Pango does the Arabic shaping + bidi, and
    # harfbuzz-subset embeds only the glyphs the invoice uses. No font package
    # here on purpose — the PDF ships its own Cairo font in invoice_assets/.
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz-subset0 \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY . .

# Create uploads directory with correct ownership
RUN mkdir -p /app/uploads /app/static/avatars \
    && chown -R appuser:appuser /app

USER appuser

# Expose internal port (Nginx will proxy to this)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# Start Gunicorn with UvicornWorkers
CMD ["gunicorn", "main:app", "--config", "gunicorn.conf.py"]
