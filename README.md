# InvenTree warehouse

Local deployment: `/home/den/server-data/inventree`.

InvenTree owns the parts catalog, stock, suppliers and storage locations. The
private WLED Locator Plus addon maps storage locations to LEDs and provides a
multi-part finder. Categories describe items; locations describe their storage.

## Documentation

| Guide | Read it for |
|---|---|
| [Warehouse](docs/warehouse.md) | Part entry, supplier sources, parameters, stock and physical storage rules. |
| [Addon](docs/wled-locator-plus.md) | Finder, mapping, controller setup, architecture, APIs and development checks. |
| [Maintenance](docs/inventree-maintenance.md) | Deployment files, backup, restore, updates and troubleshooting. |
| [Category/location snapshot](docs/inventree-category-locations.md) | Dated placement reference; verify current stock in InvenTree. |

For inventory work, read the warehouse guide and query only relevant live records.
For addon work, also read the addon guide. Routine part entry needs no restart.
User instructions define the scope; analysis is read-only and changes require
authorization. Hardware commands must follow an explicitly requested action.

## Files and data

| Path | Purpose |
|---|---|
| [docker-compose.yml](docker-compose.yml) | Database, cache, application, worker and Caddy services. |
| [docker-compose.override.yml](docker-compose.override.yml) | External `proxy_net` connection and proxy port overrides. |
| [Caddyfile](Caddyfile) | Application proxy and static/media serving. |
| [manual-inventree-backup.sh](manual-inventree-backup.sh) | Native database/media backup and recent-file check. |
| [prune-inventree-backups.sh](prune-inventree-backups.sh) | Backup retention; dry run by default, ten-day cutoff. |
| [update-inventree.sh](update-inventree.sh) | Stop, pull images, run update tasks, start. |
| [.gitignore](.gitignore) | Excludes secrets, runtime data and generated files. |
| [Addon source](data/plugins/inventree_wled_locator_plus/) | Transferable custom plugin, UI assets and tests. |
| `data/plugins/__init__.py` | Local plugin package marker. |
| `data/plugins.txt` | Additional supplier-panel dependency. |
| `.env`, `data/config.yaml` | Deployment/application configuration; may contain secrets. |
| `data/secret_key.txt`, `data/oidc.pem` | Application secret and authentication key material. |
| `data/pgdb/`, `data/media/`, `data/backup/` | Database storage, uploaded inventory files and backups. |
| `data/static/`, `data/redis/`, `data/caddy/` | Collected assets, cache and proxy runtime data. |
| `data/data.json`, `inventree-before-db-password-change.sql` | Data exports; not authoritative live inventory or guides. |
| `Downloads/` | Connector PDFs and a Proxmox screenshot used as reference material. |
| `EEParts/` | Empty at the documentation review. |

Documentation maintenance covers the project guides. Third-party licences under
`data/static/` belong to their distributed assets. Source, configuration, exports,
uploads and backups have separate lifecycles; an old file is not automatically
safe to delete.

## Current scope

Typed combined search, match images, value normalization, selection recovery,
native locate panels and mapping tools are implemented. Voice recording,
speech-to-text integration and general parameter filtering are not implemented.
Whisper hosted locally through Speaches or another speech server is under
consideration; no service/model choice or deployment is finalized.
