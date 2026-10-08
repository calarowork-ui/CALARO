#!/usr/bin/env bash
# Nightly MongoDB backup. Keeps the newest 14 archives in ./backups.
# Install:  crontab -e   then add:   0 3 * * * /home/ubuntu/calaro/deploy/backup.sh >> /home/ubuntu/calaro/backups/backup.log 2>&1
# Restore:  docker compose exec -T mongo mongorestore --archive --gzip --drop < backups/calaro-YYYY-MM-DD-HHMM.archive.gz
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
stamp=$(date +%F-%H%M)
docker compose exec -T mongo mongodump --archive --gzip --db calaro > "backups/calaro-$stamp.archive.gz"
ls -1t backups/calaro-*.archive.gz | tail -n +15 | xargs -r rm --
echo "$(date -Is) backup ok: backups/calaro-$stamp.archive.gz"
