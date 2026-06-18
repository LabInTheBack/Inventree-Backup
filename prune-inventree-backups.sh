#!/usr/bin/env bash
set -euo pipefail

# InvenTree backup cleanup script
#
# Default behavior:
#   Dry-run mode. Prints files that would be deleted.
#
# Delete mode:
#   Run with --delete to actually delete old backup files.
#
# Example:
#   ./prune-inventree-backups.sh
#   ./prune-inventree-backups.sh --delete

BACKUP_DIR="/home/den/server-data/inventree/data/backup"
RETENTION_DAYS=10

if [[ "${1:-}" == "--delete" ]]; then
    DELETE_MODE=true
else
    DELETE_MODE=false
fi

echo "InvenTree backup cleanup"
echo "Backup directory: $BACKUP_DIR"
echo "Retention: files older than $RETENTION_DAYS days"
echo

if [[ ! -d "$BACKUP_DIR" ]]; then
    echo "ERROR: Backup directory does not exist: $BACKUP_DIR" >&2
    exit 1
fi

if [[ "$DELETE_MODE" == true ]]; then
    echo "DELETE MODE ENABLED"
    echo "The following files will be deleted:"
    echo

    find "$BACKUP_DIR" -type f \
        \( -name "InvenTree-db-*" -o -name "InvenTree-media-*" \) \
        -mtime +"$RETENTION_DAYS" \
        -print \
        -delete

    echo
    echo "Cleanup complete."
else
    echo "DRY RUN MODE"
    echo "The following files would be deleted:"
    echo

    find "$BACKUP_DIR" -type f \
        \( -name "InvenTree-db-*" -o -name "InvenTree-media-*" \) \
        -mtime +"$RETENTION_DAYS" \
        -print

    echo
    echo "Dry run complete. No files were deleted."
    echo "Run with --delete to actually delete these files:"
    echo "$0 --delete"
fi
