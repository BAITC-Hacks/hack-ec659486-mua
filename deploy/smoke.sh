#!/usr/bin/env bash
# Smoke: собрать, поднять, проверить. Это репетиция того, что сделает технический эксперт.
#
# По Положению 5.4.16 и 5.6.5 проект, который не запускается по инструкциям из репозитория,
# к дальнейшему отбору не допускается, и исправления не принимаются. Поэтому скрипт
# обязан падать с ненулевым кодом на первой же неудачной проверке, а не печатать OK.
#
# Принудительно LLM_MODE=mock: по 5.6.6 ключевая функциональность должна проверяться
# без личных аккаунтов и ключей проверяющего.
#
# Usage: deploy/smoke.sh            (из корня репозитория; нужна группа docker или sudo)
set -euo pipefail
cd "$(dirname "$0")/.."

export LLM_MODE=mock          # переменные окружения приоритетнее .env при интерполяции compose
BACKEND=http://localhost:8000
FRONTEND=http://localhost:3000
DEADLINE=$((SECONDS + 180))

fail() { echo "SMOKE FAILED: $*" >&2; echo "--- логи backend ---" >&2; docker compose logs --tail 40 backend >&2 || true; exit 1; }

[ -f .env ] || cp .env.example .env
docker compose up --build -d
docker compose ps

echo "== ждём готовности сервисов (до 180 с)"
until curl -fsS "$BACKEND/health" >/dev/null 2>&1 && curl -fsS -o /dev/null "$FRONTEND/" 2>/dev/null; do
  [ $SECONDS -lt $DEADLINE ] || fail "сервисы не поднялись за отведённое время"
  sleep 3
done

echo "== backend /health"
HEALTH=$(curl -fsS "$BACKEND/health") || fail "/health недоступен"
echo "$HEALTH"
grep -q '"status":"ok"' <<<"${HEALTH// /}" || fail "/health не вернул status=ok"
grep -q '"llm_mode":"mock"' <<<"${HEALTH// /}" || fail "/health не в mock-режиме: $HEALTH"

echo "== backend /api/example (основной сценарий на фикстуре)"
EXAMPLE=$(curl -fsS -X POST "$BACKEND/api/example" \
  -H 'content-type: application/json' -d '{"text":"smoke"}') || fail "POST /api/example вернул ошибку"
echo "$EXAMPLE"
grep -q '"answer"' <<<"$EXAMPLE" || fail "/api/example не вернул поле answer: $EXAMPLE"

echo "== backend: невалидный вход отвергается с 422"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BACKEND/api/example" \
  -H 'content-type: application/json' -d '{}')
[ "$CODE" = "422" ] || fail "пустой запрос дал HTTP $CODE вместо 422"

echo "== backend: ошибки не раскрывают внутренности"
NOT_FOUND=$(curl -s "$BACKEND/api/does-not-exist")
if grep -qiE 'traceback|sk-[A-Za-z0-9]' <<<"$NOT_FOUND"; then
  fail "в теле ошибки внутренние данные: $NOT_FOUND"
fi

echo "== frontend /"
curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' "$FRONTEND/" || fail "фронтенд не отвечает 2xx"

# ВАЖНО: по мере появления продуктовых эндпоинтов добавлять их сюда же.
# Сквозной сценарий, который заявлен в README, должен проверяться этим скриптом целиком.

echo
echo "SMOKE OK (остановить: docker compose down)"
