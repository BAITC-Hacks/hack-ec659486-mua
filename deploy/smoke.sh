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
BACKEND=${BACKEND:-http://localhost:8000}
FRONTEND=${FRONTEND:-http://localhost:3000}
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

echo "== backend: контрольный комплект"
CREATED=$(curl -fsS -X POST "$BACKEND/api/runs/demo") || fail "POST /api/runs/demo вернул ошибку"
RUN_ID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["run_id"])' <<<"$CREATED") || \
  fail "в ответе нет run_id: $CREATED"
[ -n "$RUN_ID" ] || fail "пустой run_id: $CREATED"

echo "== ждём анализ $RUN_ID (до 120 с)"
RUN_DEADLINE=$((SECONDS + 120))
while :; do
  RUN_STATUS=$(curl -fsS "$BACKEND/api/runs/$RUN_ID") || fail "статус запуска недоступен"
  STATE=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' \
    <<<"$RUN_STATUS") || fail "неверный ответ статуса: $RUN_STATUS"
  case "$STATE" in
    done) break ;;
    partial) fail "анализ завершился частично: $RUN_STATUS" ;;
    error) fail "анализ завершился ошибкой: $RUN_STATUS" ;;
  esac
  [ $SECONDS -lt $RUN_DEADLINE ] || fail "анализ не завершился за 120 с: $RUN_STATUS"
  sleep 2
done

REPORT=$(curl -fsS "$BACKEND/api/runs/$RUN_ID/report") || fail "отчёт недоступен"
python3 -c 'import json,sys; r=json.load(sys.stdin); required=("unit_changes","function_matches","duplicates"); missing=[key for key in required if not r.get(key)]; print("Отчёт:", {key:len(r.get(key,[])) for key in required}); sys.exit(bool(missing))' \
  <<<"$REPORT" || fail "в отчёте нет подразделений, функций или дублей"
MARKDOWN=$(curl -fsS "$BACKEND/api/runs/$RUN_ID/report.md") || fail "экспорт .md недоступен"
[ -n "$MARKDOWN" ] || fail "экспорт .md пуст"

echo "== backend: PDF отклоняется как неподдерживаемый формат"
PDF_RESPONSE=$(curl -sS -w '\n%{http_code}' -X POST "$BACKEND/api/runs" \
  -F 'before[]=@backend/tests/test_e2e_mock.py;filename=before.pdf;type=application/pdf' \
  -F 'after[]=@backend/tests/test_e2e_mock.py;filename=after.pdf;type=application/pdf') || \
  fail "не удалось проверить отказ на PDF"
PDF_CODE=${PDF_RESPONSE##*$'\n'}
PDF_BODY=${PDF_RESPONSE%$'\n'*}
[ "$PDF_CODE" = "422" ] || fail "PDF-загрузка дала HTTP $PDF_CODE вместо 422"
python3 -c 'import json,sys; sys.exit(json.load(sys.stdin).get("error") != "unsupported_format")' \
  <<<"$PDF_BODY" || fail "PDF отклонён с неверным кодом ошибки: $PDF_BODY"

echo "== backend: ошибки не раскрывают внутренности"
NOT_FOUND=$(curl -s "$BACKEND/api/does-not-exist")
if grep -qiE 'traceback|sk-[A-Za-z0-9]' <<<"$NOT_FOUND"; then
  fail "в теле ошибки внутренние данные: $NOT_FOUND"
fi

echo "== frontend /"
curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' "$FRONTEND/" || fail "фронтенд не отвечает 2xx"

echo
echo "SMOKE OK (остановить: docker compose down)"
