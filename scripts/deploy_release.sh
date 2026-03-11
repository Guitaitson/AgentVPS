#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vps-agent}"
BRANCH="${DEPLOY_BRANCH:-main}"
PIP_BIN="${PIP_BIN:-$APP_DIR/core/venv/bin/pip}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-vps-postgres}"
POSTGRES_DB="${POSTGRES_DB:-vps_agent}"
POSTGRES_USER="${POSTGRES_USER:-vps_agent}"
DEPLOY_ATTEMPT="${DEPLOY_ATTEMPT:-0}"
DEPLOY_DEFER_MINUTES="${DEPLOY_DEFER_MINUTES:-15}"
DEPLOY_MAX_DEFERRALS="${DEPLOY_MAX_DEFERRALS:-16}"
DEPLOY_BLOCKER_DIR="${DEPLOY_BLOCKER_DIR:-$APP_DIR/runtime/deploy-blockers}"

sql_count() {
  local sql
  sql="$1"
  docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At \
    -c "$sql" 2>/dev/null || echo "0"
}

has_active_voice_processing() {
  local running_jobs processing_count
  running_jobs="$(sql_count "select count(*) from voice_ingestion_jobs where status = 'running';")"
  processing_count="$(find "$APP_DIR/data/voice/processing" -type f 2>/dev/null | wc -l | tr -d ' ')"
  [[ "${running_jobs:-0}" != "0" || "${processing_count:-0}" != "0" ]]
}

has_active_runtime_work() {
  local running_missions executing_proposals running_tasks blocker_files
  running_missions="$(sql_count "select count(*) from agent_missions where status = 'running';")"
  executing_proposals="$(sql_count "select count(*) from agent_proposals where status = 'executing';")"
  running_tasks="$(sql_count "select count(*) from scheduled_tasks where status = 'running';")"
  blocker_files="$(find "$DEPLOY_BLOCKER_DIR" -type f 2>/dev/null | wc -l | tr -d ' ')"
  [[ "${running_missions:-0}" != "0" || "${executing_proposals:-0}" != "0" || "${running_tasks:-0}" != "0" || "${blocker_files:-0}" != "0" ]]
}

schedule_deferred_retry() {
  local next_attempt unit_name
  next_attempt="$((DEPLOY_ATTEMPT + 1))"
  unit_name="agentvps-release-deploy-${next_attempt}-$(date +%s)"
  systemd-run \
    --unit "$unit_name" \
    --on-active "${DEPLOY_DEFER_MINUTES}m" \
    /usr/bin/env \
    APP_DIR="$APP_DIR" \
    DEPLOY_BRANCH="$BRANCH" \
    DEPLOY_ATTEMPT="$next_attempt" \
    DEPLOY_DEFER_MINUTES="$DEPLOY_DEFER_MINUTES" \
    DEPLOY_MAX_DEFERRALS="$DEPLOY_MAX_DEFERRALS" \
    /bin/bash "$APP_DIR/scripts/deploy_release.sh"
}

cd "$APP_DIR"
mkdir -p "$DEPLOY_BLOCKER_DIR"

if has_active_voice_processing || has_active_runtime_work; then
  if (( DEPLOY_ATTEMPT >= DEPLOY_MAX_DEFERRALS )); then
    echo "deploy postponed too many times; aborting"
    exit 1
  fi
  echo "active processing detected; scheduling retry in ${DEPLOY_DEFER_MINUTES} minutes"
  schedule_deferred_retry
  exit 0
fi

git fetch origin --prune
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

"$PIP_BIN" install -e ".[dev,voice]"

docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < configs/migration-autonomous.sql
docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < configs/migration-memory-soul.sql
docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < configs/migration-skills-catalog.sql
docker exec -i "$POSTGRES_CONTAINER" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < configs/migration-voice-context.sql

mkdir -p /opt/vps-agent/data/qdrant-storage
docker network inspect vps-core-network >/dev/null 2>&1 || docker network create vps-core-network
docker compose -f configs/docker-compose.qdrant.yml up -d

cp configs/telegram-bot.service /etc/systemd/system/telegram-bot.service
cp configs/mcp-server.service /etc/systemd/system/mcp-server.service
systemctl daemon-reload
systemctl restart telegram-bot mcp-server
systemctl is-active telegram-bot mcp-server
