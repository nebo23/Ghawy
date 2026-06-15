#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  Ghawy — One-Command Production Deploy Script
#  Run this on your Hostinger KVM 2 server after initial setup
#
#  Usage:
#    chmod +x deploy.sh
#    ./deploy.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

# ── Config ─────────────────────────────────────────────────────
APP_DIR="/opt/ghawy"
COMPOSE_FILE="docker-compose.prod.yml"
GIT_BRANCH="main"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Ghawy Production Deploy          ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Check Docker ────────────────────────────────────────────
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Installing..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

if ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose v2 not found. Installing..."
    apt-get install -y docker-compose-plugin
fi

echo "✅ Docker $(docker --version | cut -d' ' -f3) ready"

# ── 2. Go to app directory ─────────────────────────────────────
cd "$APP_DIR"

# ── 3. Pull latest code ────────────────────────────────────────
echo ""
echo "📥 Pulling latest code from git..."
git fetch origin
git reset --hard origin/$GIT_BRANCH
echo "✅ Code updated to: $(git log --oneline -1)"

# ── 4. Verify .env.production exists ──────────────────────────
if [ ! -f "backend/.env.production" ]; then
    echo ""
    echo "❌ ERROR: backend/.env.production not found!"
    echo "   Copy the example and fill in your values:"
    echo "   cp backend/.env.production.example backend/.env.production"
    echo "   nano backend/.env.production"
    exit 1
fi
echo "✅ .env.production found"

# ── 5. Build & start services ──────────────────────────────────
echo ""
echo "🐳 Building Docker images..."
docker compose -f "$COMPOSE_FILE" build --no-cache

echo ""
echo "🚀 Starting services..."
docker compose -f "$COMPOSE_FILE" up -d

# ── 6. Wait for backend health ─────────────────────────────────
echo ""
echo "⏳ Waiting for backend to be healthy..."
RETRIES=15
WAIT=4
for i in $(seq 1 $RETRIES); do
    if docker compose -f "$COMPOSE_FILE" ps backend | grep -q "healthy"; then
        echo "✅ Backend is healthy!"
        break
    fi
    if [ $i -eq $RETRIES ]; then
        echo "⚠️  Backend health check timed out — check logs:"
        echo "   docker compose -f $COMPOSE_FILE logs backend --tail=50"
    fi
    echo "   Attempt $i/$RETRIES — waiting ${WAIT}s..."
    sleep $WAIT
done

# ── 7. Show status ─────────────────────────────────────────────
echo ""
echo "📊 Service Status:"
docker compose -f "$COMPOSE_FILE" ps

# ── 8. Quick smoke test ────────────────────────────────────────
echo ""
echo "🔍 Running smoke test..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/api/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ API responding: HTTP $HTTP_CODE"
else
    echo "⚠️  API returned HTTP $HTTP_CODE — check nginx and backend logs"
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  ✅ Deploy complete!                  ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "Useful commands:"
echo "  View logs:       docker compose -f $COMPOSE_FILE logs -f"
echo "  Backend logs:    docker compose -f $COMPOSE_FILE logs backend -f"
echo "  Restart:         docker compose -f $COMPOSE_FILE restart"
echo "  Stop:            docker compose -f $COMPOSE_FILE down"
echo "  DB migrations:   docker compose -f $COMPOSE_FILE exec backend alembic upgrade head"
echo ""
