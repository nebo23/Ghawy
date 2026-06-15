# Ghawy — Hostinger KVM 2 Server Setup Guide

## Prerequisites
- Hostinger KVM 2 VPS running Ubuntu 22.04 LTS
- Your domain DNS A-record pointed to the server IP
- SSH access as root

---

## Step 1 — Connect to Your Server

```bash
ssh root@YOUR_SERVER_IP
```

## Step 2 — Update & Install Git

```bash
apt-get update && apt-get upgrade -y
apt-get install -y git curl ufw
```

## Step 3 — Configure Firewall

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

## Step 4 — Clone the Repository

```bash
mkdir -p /opt/ghawy
cd /opt/ghawy
git clone https://github.com/YOUR_USERNAME/Ghawy.git .
```

## Step 5 — Install Docker

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Verify
docker --version
docker compose version
```

## Step 6 — Create Production Environment File

```bash
cp /opt/ghawy/backend/.env.production.example /opt/ghawy/backend/.env.production
nano /opt/ghawy/backend/.env.production
```

Fill in every `<CHANGE_ME>` value:

| Variable | What to put |
|----------|-------------|
| `DATABASE_URL` | `postgresql://ghawy_user:YOUR_PASS@postgres:5432/ghawy_db` |
| `POSTGRES_PASSWORD` | A strong password (save it!) |
| `SECRET_KEY` | Run: `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ALLOWED_ORIGINS` | `https://yourdomain.com,https://www.yourdomain.com` |
| `FRONTEND_URL` | `https://yourdomain.com` |
| `KASHIER_RETURN_URL` | `https://yourdomain.com/api/payment/kashier/success` |
| `KASHIER_FAILURE_URL` | `https://yourdomain.com/api/payment/kashier/fail` |
| `KASHIER_WEBHOOK_URL` | `https://yourdomain.com/api/webhooks/kashier` |

## Step 7 — Update Nginx Config with Your Domain

```bash
nano /opt/ghawy/nginx/nginx.conf
```

Find `server_name _;` and replace with:
```nginx
server_name yourdomain.com www.yourdomain.com;
```

## Step 8 — Run the Deploy Script

```bash
chmod +x /opt/ghawy/deploy.sh
cd /opt/ghawy
./deploy.sh
```

Wait ~2 minutes for Docker to build everything.

## Step 9 — Verify It's Working

```bash
# Test API
curl http://YOUR_SERVER_IP/api/
# Expected: {"message": "Community API Is Working"}

# Test frontend
curl -I http://YOUR_SERVER_IP/
# Expected: HTTP/1.1 200 OK

# Check all containers are running
docker compose -f docker-compose.prod.yml ps
```

---

## Step 10 (Optional but Recommended) — Set Up Free SSL with Let's Encrypt

```bash
apt-get install -y certbot
certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Then uncomment the SSL section in nginx/nginx.conf and restart:
docker compose -f docker-compose.prod.yml restart nginx
```

---

## Future Deployments

Every time you push code, just run on the server:

```bash
cd /opt/ghawy && ./deploy.sh
```

---

## Useful Commands

```bash
# View live logs
docker compose -f docker-compose.prod.yml logs -f

# Backend logs only
docker compose -f docker-compose.prod.yml logs backend -f

# Restart everything
docker compose -f docker-compose.prod.yml restart

# Run DB migrations manually
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Connect to DB
docker compose -f docker-compose.prod.yml exec postgres psql -U ghawy_user -d ghawy_db

# Stop everything
docker compose -f docker-compose.prod.yml down
```
