#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vps-agent}"
BRANCH="${DEPLOY_BRANCH:-main}"
PIP_BIN="${PIP_BIN:-$APP_DIR/core/venv/bin/pip}"
POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-vps-postgres}"
POSTGRES_DB="${POSTGRES_DB:-vps_agent}"
POSTGRES_USER="${POSTGRES_USER:-vps_agent}"

cd "$APP_DIR"

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
