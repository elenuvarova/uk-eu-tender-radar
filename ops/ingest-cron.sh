#!/usr/bin/env bash
# Weekly PRODUCTION ingestion for uk-eu-tender-radar.
#
# Why this exists: prod Postgres runs on the Hetzner box's internal Coolify
# Docker network and is NOT reachable from a GitHub Actions runner, so the
# ingestion has to run *on the server*. This script lives in the root crontab
# and `docker exec`s into the live application container (which already has the
# correct internal DATABASE_URL in its environment).
#
# The container name carries a random suffix that changes on every redeploy, so
# we resolve it fresh each run by the stable Coolify application-UUID prefix.
#
# Install on the server:
#   scp ops/ingest-cron.sh root@<host>:/root/ingest-cron.sh
#   chmod +x /root/ingest-cron.sh
#   ( crontab -l 2>/dev/null; echo '0 6 * * 1 /root/ingest-cron.sh' ) | crontab -
#
# Schedule: Monday 06:00 UTC (after TED + FTS publish overnight notices).
set -euo pipefail

APP_UUID="pwo2fat5ma68e877ggzc1vpn"   # Coolify application UUID for tenderhub
LOG="/var/log/tenderhub-ingest.log"
DAYS="${DAYS:-8}"

ts() { date -u +'%Y-%m-%dT%H:%M:%SZ'; }

{
  CID="$(docker ps --filter "name=${APP_UUID}" --format '{{.Names}}' | head -n1)"
  if [ -z "$CID" ]; then
    echo "$(ts) ERROR: no running container found for ${APP_UUID}"
    exit 1
  fi
  echo "$(ts) START ingestion in ${CID} (days=${DAYS})"
  docker exec "$CID" python -m app.ingestion.run --source fts --days "$DAYS" --niche-only
  docker exec "$CID" python -m app.ingestion.run --source ted --days "$DAYS" --niche-only
  echo "$(ts) DONE ingestion"
} >> "$LOG" 2>&1
