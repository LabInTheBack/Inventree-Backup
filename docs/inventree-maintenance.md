# Deployment and maintenance

Workspace: `/home/den/server-data/inventree`. Run the commands below from that
directory. Inventory procedures are in [warehouse.md](warehouse.md); plugin
changes and asset activation are in [wled-locator-plus.md](wled-locator-plus.md).
Routine inventory entry and documentation edits require no restart.

## Deployment files and storage

| File/service | Role |
|---|---|
| [docker-compose.yml](../docker-compose.yml) | `inventree-server`, `inventree-worker`, PostgreSQL 17, Redis 7 and Caddy. InvenTree image tag comes from `INVENTREE_TAG`. |
| [docker-compose.override.yml](../docker-compose.override.yml) | Server/proxy join external `proxy_net`; Caddy's host ports are reset. Preserve this topology when changing routing. |
| [Caddyfile](../Caddyfile) | Proxies the application, serves static files and authenticates media requests through InvenTree. |
| `.env`, `data/config.yaml` | Environment/application settings, including sensitive values. Do not copy their contents into documentation. |
| `data/secret_key.txt`, `data/oidc.pem` | Secret/key material that must survive a deployment restore. |
| `data/plugins/`, `data/plugins.txt` | Custom plugin source and additional supplier-panel dependency. |
| `data/media/`, `data/pgdb/`, `data/backup/` | Uploaded assets, PostgreSQL data and native backups. The data mount appears as `/home/inventree/data` inside InvenTree. |
| `data/static/`, `data/redis/`, `data/caddy/` | Generated/static assets, cache and proxy state. Redis is not the inventory source of truth. |

The Caddy mounts also use the shared data directory for logs and proxy state;
consult Compose before moving files. The external proxy/network configuration is
outside this repository. The application uses Django, PostgreSQL and Redis;
`data/data.json` and root SQL dumps are exports, not live inventory.

## Inspect status

```bash
cd /home/den/server-data/inventree
docker compose ps
docker compose images
docker compose logs --tail=100 inventree-server inventree-worker
df -h .
du -sh data/media data/backup
docker compose exec -T inventree-db sh -c \
  'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Check repeated restarts, database/migration errors, missing media, permissions,
worker failures and disk space. Logs may contain sensitive data; inspect locally
and redact excerpts before sharing. This guide does not assert that schedules,
off-server copies or a successful restore test are already configured.

## Back up

Use the existing [manual backup script](../manual-inventree-backup.sh):

```bash
cd /home/den/server-data/inventree
bash ./manual-inventree-backup.sh
```

It runs native database/media backup and lists the results. Its final check only
requires files within the recent-file window (two days by default); it does not
prove archive integrity or a successful restore. Defaults are this workspace and
`data/backup`; `INVENTREE_DIR`, `BACKUP_DIR` and `RETENTION_CHECK_DAYS` can override
the script's paths/check window.

For a manual listing:

```bash
docker compose run --rm inventree-server invoke listbackups
```

Copy the selected database and media archives to separate storage. Also preserve
both Compose files, `.env`, `Caddyfile`, scripts, documentation, `data/config.yaml`,
secret/key files, custom plugins and dependency list. Native database/media
archives do not replace that deployment-file backup. Protect copies containing
credentials or inventory data. A live copy of `data/pgdb/` is not a substitute for
a database backup. Test restoration on an isolated instance before relying on it.

## Retention

[prune-inventree-backups.sh](../prune-inventree-backups.sh) uses `find -mtime +10`
for `InvenTree-db-*` and `InvenTree-media-*` files under `data/backup`. Review first:

```bash
bash ./prune-inventree-backups.sh
```

Only add `--delete` when intentionally deleting the listed files. The script does
not implement weekly/monthly tiers, off-server copies or scheduling. Keep any
long-term copies outside its target directory. No cron entries in this guide
should be interpreted as jobs installed on the server.

## Restore

Restore replaces data; test on a separate instance first. Use the backup's
InvenTree version and restore the deployment configuration, secret/key files and
plugin source as well as database/media. Plugin settings and WLED location
metadata live in the database. Use explicit matching archive filenames rather
than allowing selection of unrelated latest files.

For an authorized deployment restore, put the chosen archives in `data/backup`
and replace both uppercase filenames below with actual basenames:

```bash
cd /home/den/server-data/inventree
docker compose stop inventree-server inventree-worker inventree-proxy
docker compose up -d inventree-db inventree-cache
docker compose run --rm inventree-server invoke restore \
  --path /home/inventree/data/backup \
  --db-file DATABASE_BACKUP_FILENAME \
  --media-file MEDIA_BACKUP_FILENAME
docker compose up -d
```

These task options were checked against the installed `tasks.py`; the procedure
has not been exercised as a restore test during documentation cleanup. After a
successful restore, check login, parts/stock, images/attachments, worker, plugin
settings and mappings. Physical locate testing remains an explicit hardware action.

## Update and rollback

1. Record the current image version, take a fresh database/media backup and copy
   it plus deployment files off-server before pulling a replacement image.
2. Choose the intended `INVENTREE_TAG`; a pinned release makes rollback clearer
   than a moving tag. Preserve the external network and persistent mounts.
3. Run the existing [update script](../update-inventree.sh) in the maintenance
   window: `bash ./update-inventree.sh`.
4. Inspect status/logs and verify login, stock, uploads, plugin pages and worker.

The wrapper stops the stack, pulls images, runs `invoke update` and starts it.
The installed update task backs up by default unless `--skip-backup` is passed,
but that happens after the new image has been pulled. It does not replace the
explicit backup made using the previous working deployment or its off-server copy.
If the script fails, inspect the failure; it may leave services stopped.

For rollback, stop application writes, restore the recorded previous image tag
and the matching pre-update database/media/configuration/plugin backup, then
start and verify. Downgrading only the image may not reverse schema changes.

Backup/restore/static command behaviour above was checked against installed
source on 2026-11-11. Recheck `invoke TASK --help` when upgrading InvenTree.
