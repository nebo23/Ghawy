#!/bin/bash
# Ghawy backups — database daily, uploads weekly.
#
# Added 2026-08-15. Until then nothing here was scheduled: the only database
# file on disk was a one-off dump of the users table taken by hand before a
# migration, and the newest copy of uploads/ was a month old. 1450 members,
# 1190 payments and 10066 messages had no recoverable copy, which was a larger
# risk to the business than anything the security review turned up.
#
# The database is ~27MB and compresses to a few MB, so a daily dump with a
# month of history costs almost nothing against 173GB free. uploads/ is ~1.1GB
# of member-uploaded receipts, avatars and course art — too big to copy daily,
# rarely changing, so it runs weekly with four generations kept.
#
# Restore:
#   database:  docker exec -i ghawy_postgres pg_restore -U <user> -d <db> --clean < db-YYYY-MM-DD.dump
#   uploads:   tar xzf uploads-YYYY-MM-DD.tar.gz -C /var/lib/docker/volumes/ghawy_uploads_data/_data
set -euo pipefail

BACKUP_DIR=/opt/ghawy/backups
DB_KEEP_DAYS=30
UPLOADS_KEEP=4
UPLOADS_SOURCE=/var/lib/docker/volumes/ghawy_uploads_data/_data

cd /opt/ghawy
set -a; . ./.env; set +a

stamp=$(date -u +%Y-%m-%d_%H%M)
log() { logger -t ghawy-backup "$*"; echo "$(date -u +%H:%M:%S) $*"; }

# ── Database ────────────────────────────────────────────────────────────────
# Custom format (-Fc): compressed on its own, and pg_restore can list or pull
# single tables out of it without unpacking the whole dump.
db_file="$BACKUP_DIR/db-$stamp.dump"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" ghawy_postgres \
    pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$db_file"

# A dump that cannot be listed cannot be restored. Check before trusting it,
# and never let a corrupt file sit in the directory looking like a backup.
# pg_restore lives in the container, not on the host, and reads the archive
# from stdin when given no file argument.
if ! docker exec -i ghawy_postgres pg_restore -l < "$db_file" >/dev/null 2>&1; then
    rm -f "$db_file"
    log "FAILED: database dump did not verify, removed"
    exit 1
fi
log "database OK: $(basename "$db_file") ($(du -h "$db_file" | cut -f1))"

find "$BACKUP_DIR" -maxdepth 1 -name 'db-*.dump' -mtime +$DB_KEEP_DAYS -delete

# ── Uploads, Sundays only ───────────────────────────────────────────────────
if [[ "$(date -u +%u)" == "7" ]]; then
    up_file="$BACKUP_DIR/uploads-$stamp.tar.gz"
    tar czf "$up_file" -C "$UPLOADS_SOURCE" .
    if tar tzf "$up_file" >/dev/null 2>&1; then
        log "uploads OK: $(basename "$up_file") ($(du -h "$up_file" | cut -f1))"
        # Keep the newest UPLOADS_KEEP archives, drop the rest.
        ls -1t "$BACKUP_DIR"/uploads-*.tar.gz 2>/dev/null \
            | tail -n +$((UPLOADS_KEEP + 1)) | xargs -r rm -f
    else
        rm -f "$up_file"
        log "FAILED: uploads archive did not verify, removed"
        exit 1
    fi
fi

log "done — $(ls -1 "$BACKUP_DIR"/db-*.dump 2>/dev/null | wc -l) database backups on disk"
