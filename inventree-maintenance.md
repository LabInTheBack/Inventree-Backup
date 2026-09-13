# InvenTree Maintenance Guide

## Current Workspace Note

For catalog/database work, use [part creation rules](docs/part-creation-rules.md) and the [conversation handoff](docs/inventree-handoff.md). The active workspace is `/home/den/server-data/inventree`; the `/home/denys/inventree` paths below are historical deployment examples, not verified commands for this instance. Inspect the current Compose configuration before infrastructure work. Routine part entry does not require container restarts or updates.

This guide is for the local Docker Compose deployment of InvenTree with PostgreSQL, Redis, Caddy, and bind-mounted persistent data.

Primary goal: never depend on Docker containers as storage. Containers can be recreated; the database, media, configuration, secrets, and plugins must be backed up.

## Backup Strategy

### What To Back Up

Back up these items:

```text
/home/denys/inventree/docker-compose.yml
/home/denys/inventree/.env
/home/denys/inventree/Caddyfile
/home/denys/inventree/AGENTS.md
/home/denys/inventree/README.md
/home/denys/inventree/docs/
/home/denys/inventree/inventree-data/config.yaml
/home/denys/inventree/inventree-data/secret_key.txt
/home/denys/inventree/inventree-data/media/
/home/denys/inventree/inventree-data/plugins/
/home/denys/inventree/inventree-data/backup/
```

Also back up the PostgreSQL database using InvenTree's backup command or `pg_dump`.

Do not rely on a live copy of `inventree-data/pgdb/` as the only database backup. A live filesystem copy of PostgreSQL data can be inconsistent. Use InvenTree backup or `pg_dump`.

Redis data in `inventree-data/redis/` is cache data and is not the main source of truth.

### Schedule

Recommended minimum:

```text
Daily: InvenTree native backup of database + media.
Daily: Copy newest backup files to another machine, NAS, external disk, or cloud storage.
Weekly: Full archive of Compose files, .env, docs, config, secret key, plugins, media, and backup folder.
Monthly: Test restore on a separate throwaway instance.
```

Keep at least:

```text
7 daily backups
4 weekly backups
3 monthly backups
```

### Manual Backup

The reusable manual backup script is:

```text
docs/manual-inventree-backup.sh
```

It defaults to the other InvenTree instance layout:

```text
INVENTREE_DIR=/home/den/server-data/inventree
BACKUP_DIR=/home/den/server-data/inventree/data/backup
```

Run it like this:

```bash
bash docs/manual-inventree-backup.sh
```

For this local `/home/denys/inventree` deployment:

```bash
cd /home/denys/inventree
INVENTREE_DIR=/home/denys/inventree BACKUP_DIR=/home/denys/inventree/inventree-data/backup bash docs/manual-inventree-backup.sh
```

The script creates a native InvenTree backup and verifies that recent database and media backup files exist. Use a separate copy command or sync job to move the backup folder to external storage.

Run from the Compose directory:

```bash
cd /home/denys/inventree
docker compose run --rm inventree-server invoke backup
docker compose run --rm inventree-server invoke listbackups
```

This uses InvenTree's native backup system for database and media files.

Optional raw PostgreSQL dump:

```bash
cd /home/denys/inventree
mkdir -p /home/denys/inventree-backups
docker compose exec -T inventree-db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > /home/denys/inventree-backups/inventree-postgres-$(date +%F-%H%M).sql.gz
```

Weekly configuration and file archive:

```bash
cd /home/denys/inventree
mkdir -p /home/denys/inventree-backups
tar --exclude='inventree-data/pgdb' --exclude='inventree-data/redis' --exclude='__pycache__' -czf /home/denys/inventree-backups/inventree-files-$(date +%F-%H%M).tgz docker-compose.yml .env Caddyfile AGENTS.md README.md docs inventree-data/config.yaml inventree-data/secret_key.txt inventree-data/media inventree-data/plugins inventree-data/backup
```

### Automated Backup

Example cron entries:

```cron
15 2 * * * cd /home/denys/inventree && docker compose run --rm inventree-server invoke backup --quiet >> /home/denys/inventree/inventree-data/backup/backup.log 2>&1
45 2 * * * rsync -a --delete /home/denys/inventree/inventree-data/backup/ /mnt/backup/inventree/native/
30 3 * * 0 cd /home/denys/inventree && tar --exclude='inventree-data/pgdb' --exclude='inventree-data/redis' --exclude='__pycache__' -czf /mnt/backup/inventree/files/inventree-files-$(date +\%F).tgz docker-compose.yml .env Caddyfile AGENTS.md README.md docs inventree-data/config.yaml inventree-data/secret_key.txt inventree-data/media inventree-data/plugins inventree-data/backup
```

Replace `/mnt/backup` with a real backup disk, NAS mount, or synced folder. Do not store the only backup on the same disk or Docker VM.

Protect backup storage like a password vault. The archives include `.env`, `secret_key.txt`, database contents, uploaded files, and plugin settings.

### Backup Verification

Check that backups exist:

```bash
cd /home/denys/inventree
docker compose run --rm inventree-server invoke listbackups
ls -lh inventree-data/backup
find inventree-data/backup -type f -mtime -2 -ls
```

Check the weekly archive can be read:

```bash
tar -tzf /mnt/backup/inventree/files/inventree-files-YYYY-MM-DD.tgz | head
```

Check a raw PostgreSQL dump:

```bash
gzip -t /home/denys/inventree-backups/inventree-postgres-YYYY-MM-DD-HHMM.sql.gz
```

Best verification: restore the newest backup into a separate test InvenTree instance before entering important production data.

## Restore Strategy

Restore should be tested before serious use. The first restore test is more important than any backup schedule.

Basic restore pattern:

```bash
cd /home/denys/inventree
docker compose down
```

Restore the deployment files first:

```bash
tar -xzf /path/to/inventree-files-YYYY-MM-DD.tgz -C /home/denys/inventree
```

Place the selected InvenTree database and media backup files in:

```text
/home/denys/inventree/inventree-data/backup/
```

Run restore:

```bash
cd /home/denys/inventree
docker compose run --rm inventree-server invoke restore
docker compose up -d
```

If restoring specific files:

```bash
cd /home/denys/inventree
docker compose run --rm inventree-server invoke restore -p /home/inventree/data/backup --db-file <database-backup-file> --media-file <media-backup-file>
docker compose up -d
```

After restore:

```bash
docker compose ps
docker compose logs --tail=100 inventree-server
docker compose logs --tail=100 inventree-worker
```

Check in the UI:

```text
Login works.
Parts and stock records exist.
Uploaded images/files load.
Plugins load.
WLED controller settings and StockLocation metadata are present if the database was restored.
```

### Restore Mistakes To Avoid

Avoid these:

* Restoring with a different InvenTree version than the backup was created with.
* Restoring only the database and forgetting media uploads.
* Losing `secret_key.txt`; keep the same key for the same deployment.
* Treating `inventree-data/pgdb/` copied while PostgreSQL is running as a reliable backup.
* Keeping backups only inside the same VM, disk, or Docker volume.
* Running destructive test restores on the real production instance.
* Updating first and only then checking whether backups are usable.

## Update Strategy

Update when there is a useful bug fix, security fix, or planned maintenance window. For a low-admin home deployment, monthly or every few months is reasonable. Avoid using `latest` for serious data. Prefer `stable` or a pinned release tag, and record the version before updating.

Before every update:

```bash
cd /home/denys/inventree
docker compose ps
docker compose images
docker compose run --rm inventree-server invoke backup
docker compose run --rm inventree-server invoke listbackups
```

Copy backups off the server before continuing.

Safe update procedure:

```bash
cd /home/denys/inventree
docker compose down
docker compose pull
docker compose run --rm inventree-server invoke update
docker compose up -d
```

After update:

```bash
docker compose ps
docker compose logs --tail=100 inventree-server
docker compose logs --tail=100 inventree-worker
docker compose logs --tail=100 inventree-db
```

Check in the UI:

```text
Login works.
Parts, stock, images, reports, and plugins load.
Background worker is running.
No repeated errors appear in logs.
```

Rollback if an update breaks:

1. Stop containers.
2. Set `INVENTREE_TAG` in `.env` back to the previous known-good tag.
3. Pull that image.
4. Restore the backup created immediately before the update.
5. Start containers.

Commands:

```bash
cd /home/denys/inventree
docker compose down
docker compose pull
docker compose run --rm inventree-server invoke restore
docker compose up -d
```

Rollback is much easier if `INVENTREE_TAG` is pinned to a specific release instead of floating on `stable`.

## Monitoring And Maintenance

### Container Health

```bash
cd /home/denys/inventree
docker compose ps
docker compose logs --tail=100 inventree-server
docker compose logs --tail=100 inventree-worker
docker compose logs --tail=100 inventree-db
docker compose logs --tail=100 inventree-cache
```

Warning signs:

```text
Containers restarting repeatedly.
Database connection errors.
Migration errors.
Permission errors under /home/inventree/data.
Worker not running.
Repeated backup failures.
HTTP 500 errors.
Missing media/static file errors.
```

### Disk Usage

```bash
df -h /home/denys/inventree
du -sh /home/denys/inventree/inventree-data
du -sh /home/denys/inventree/inventree-data/media
du -sh /home/denys/inventree/inventree-data/backup
docker system df
```

Do not let the disk fill up. PostgreSQL and backups can both fail badly on a full disk.

### Database Status

```bash
cd /home/denys/inventree
docker compose exec inventree-db sh -c 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

### Backup Health

```bash
cd /home/denys/inventree
docker compose run --rm inventree-server invoke listbackups
find inventree-data/backup -type f -mtime -2 -ls
ls -lh /mnt/backup/inventree/native 2>/dev/null
ls -lh /mnt/backup/inventree/files 2>/dev/null
```

## Practical Checklist

### Daily

```bash
cd /home/denys/inventree
docker compose ps
find inventree-data/backup -type f -mtime -2 -ls
df -h /home/denys/inventree
```

Confirm containers are up, a recent backup exists, and disk space is not low.

### Weekly

```bash
cd /home/denys/inventree
docker compose run --rm inventree-server invoke listbackups
du -sh inventree-data inventree-data/media inventree-data/backup
tar -tzf /mnt/backup/inventree/files/inventree-files-YYYY-MM-DD.tgz | head
```

Confirm backups are visible, off-server copy exists, and the weekly archive can be opened.

### Before Every Update

```bash
cd /home/denys/inventree
docker compose ps
docker compose images
docker compose run --rm inventree-server invoke backup
docker compose run --rm inventree-server invoke listbackups
rsync -a inventree-data/backup/ /mnt/backup/inventree/native/
```

Only update after the fresh backup is copied off the server.

### After Every Update

```bash
cd /home/denys/inventree
docker compose ps
docker compose logs --tail=100 inventree-server
docker compose logs --tail=100 inventree-worker
```

Then log in and check records, uploads, plugins, and the worker.

## Official References

Official InvenTree documentation used for this guide:

* Docker production install: `https://docs.inventree.org/en/latest/start/docker_install/`
* Docker setup and persistent data: `https://docs.inventree.org/en/latest/start/docker/`
* Backup and restore: `https://docs.inventree.org/en/latest/start/backup/`
* Configuration and file storage: `https://docs.inventree.org/en/latest/start/config/`
* Invoke tool in Docker mode: `https://docs.inventree.org/en/latest/start/invoke/`
