#!/usr/bin/env bash
# Pull the latest code and rebuild. Data volumes are kept.
set -euo pipefail
cd "$(dirname "$0")/.."
git pull --ff-only
docker compose up --build -d
docker image prune -f >/dev/null
docker compose ps
