#!/usr/bin/env bash
set -euo pipefail

# Simple manual InvenTree backup script.
#
# It does two things:
#   1. Runs InvenTree's native backup command.
#   2. Checks that recent database and media backup files exist.
#
# Usage:
#   INVENTREE_DIR=/home/den/server-data/inventree \
#   BACKUP_DIR=/home/den/server-data/inventree/data/backup \
#   bash manual-inventree-backup.sh

INVENTREE_DIR="${INVENTREE_DIR:-/home/den/server-data/inventree}"
BACKUP_DIR="${BACKUP_DIR:-$INVENTREE_DIR/data/backup}"
RETENTION_CHECK_DAYS="${RETENTION_CHECK_DAYS:-2}"

echo "InvenTree manual backup"
echo "InvenTree directory: $INVENTREE_DIR"
echo "Backup directory: $BACKUP_DIR"
echo

if [[ ! -d "$INVENTREE_DIR" ]]; then
    echo "ERROR: InvenTree directory does not exist: $INVENTREE_DIR" >&2
    exit 1
fi

if [[ ! -f "$INVENTREE_DIR/docker-compose.yml" ]]; then
    echo "ERROR: docker-compose.yml not found in: $INVENTREE_DIR" >&2
    exit 1
fi

if [[ ! -d "$BACKUP_DIR" ]]; then
    echo "ERROR: Backup directory does not exist: $BACKUP_DIR" >&2
    exit 1
fi

cd "$INVENTREE_DIR"

echo "Creating InvenTree backup..."
docker compose run --rm inventree-server invoke backup
echo

echo "Available InvenTree backups:"
docker compose run --rm inventree-server invoke listbackups
echo

recent_db_count="$(
    find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type f \
        -name "InvenTree-db-*" \
        -mtime "-$RETENTION_CHECK_DAYS" \
        | wc -l
)"

recent_media_count="$(
    find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type f \
        -name "InvenTree-media-*" \
        -mtime "-$RETENTION_CHECK_DAYS" \
        | wc -l
)"

if (( recent_db_count < 1 )); then
    echo "ERROR: No recent InvenTree database backup file found." >&2
    exit 1
fi

if (( recent_media_count < 1 )); then
    echo "ERROR: No recent InvenTree media backup file found." >&2
    exit 1
fi

echo "Backup check passed."
echo "Recent database backup files: $recent_db_count"
echo "Recent media backup files: $recent_media_count"
