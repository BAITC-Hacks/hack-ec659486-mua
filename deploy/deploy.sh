#!/usr/bin/env bash
# Деплой с ноутбука:  deploy/deploy.sh root@IP
# Первый раз перед этим на VPS должен отработать deploy/vps-bootstrap.sh (создаёт /opt/app, docker, swap, ufw).
set -euo pipefail
HOST=${1:?usage: deploy/deploy.sh user@host}
cd "$(dirname "$0")/.."
# .env* целиком: --exclude .env не закрывал .env.local и .env.production.
# .env.example нужен на сервере, поэтому включён обратно явно.
rsync -az --delete \
  --exclude .git --exclude .venv --exclude node_modules --exclude .next \
  --include '.env.example' --exclude '.env*' \
  --exclude 'data/runtime' --exclude 'data/oulad' --exclude 'data/uci' \
  --exclude __pycache__ --exclude .pytest_cache --exclude .ruff_cache \
  ./ "$HOST:/opt/app/"
ssh "$HOST" 'cd /opt/app
  if [ ! -f .env ]; then
    cp .env.example .env
    echo "!!! Заполни /opt/app/.env на сервере (DOMAIN, OPENAI_API_KEY, LLM_MODE=live) и запусти деплой снова"
    exit 1
  fi
  docker compose -f docker-compose.prod.yml up -d --build --remove-orphans && docker compose -f docker-compose.prod.yml ps'
