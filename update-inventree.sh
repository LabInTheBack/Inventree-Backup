#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Stopping InvenTree containers..."
docker compose down

echo "Pulling updated Docker images..."
docker compose pull

echo "Running InvenTree update tasks..."
docker compose run --rm inventree-server invoke update "$@"

echo "Starting InvenTree containers..."
docker compose up -d

echo "InvenTree update complete."
