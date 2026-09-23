#!/usr/bin/env bash
# S21. Аудит кода каждые 30 минут — полуавтоматически.
#
# Агенты запускаются только в интерфейсе, поэтому запустить их по таймеру нельзя.
# Скрипт делает всё, кроме самого запроса: собирает контекст в один файл для вставки
# и потом коммитит ваш ответ в ветку ops/audit. В main не пишет никогда.
#
#   scripts/ops/audit.sh prep            # собрать контекст -> печатает путь к файлу
#   scripts/ops/audit.sh save 1530       # закоммитить заполненный reports/audit-1530.md
#   scripts/ops/audit.sh list            # что уже собрано и что ещё не заполнено
#
# Порядок на чекине (занимает минуту):
#   1) scripts/ops/audit.sh prep
#   2) содержимое context/audit-HHMM.md целиком вставить в окно агента
#   3) ответ агента вставить в reports/audit-HHMM.md (файл уже создан пустым)
#   4) scripts/ops/audit.sh save HHMM
set -uo pipefail
CMD=${1:-prep}
# у save второй аргумент — метка времени, путь к worktree тогда третий
if [ "$CMD" = "save" ]; then
  TS_ARG=${2:?укажите метку времени, например: scripts/ops/audit.sh save 1530}
  WT=${3:-../wt-ops}
else
  WT=${2:-../wt-ops}
fi
MAX_DIFF_LINES=${MAX_DIFF_LINES:-1500}

ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
[ -d "$WT/reports" ] || { echo "нет $WT/reports — сначала: scripts/ops/init-ops-branch.sh" >&2; exit 1; }
mkdir -p "$WT/context"
STATE="$WT/.last-audit-sha"

case "$CMD" in
  prep)
    PROMPT_FILE="$ROOT/prompts/ops_audit.md"
    [ -f "$PROMPT_FILE" ] || { echo "нет $PROMPT_FILE" >&2; exit 1; }
    NOW=$(date +%H:%M); TS=$(date +%H%M)
    git fetch -q origin main 2>/dev/null || echo "fetch не прошёл, смотрю локальное состояние"
    HEAD_SHA=$(git rev-parse --short origin/main 2>/dev/null || git rev-parse --short main)
    SINCE=$(cat "$STATE" 2>/dev/null || echo "")
    RANGE=${SINCE:+$SINCE..}$HEAD_SHA

    CTX="$WT/context/audit-$TS.md"
    {
      cat "$PROMPT_FILE"
      echo
      echo "---"
      echo
      echo "Текущее время: $NOW. SHA: $HEAD_SHA. Интервал: ${SINCE:-начало}..$HEAD_SHA"
      echo
      echo '=== docs/case.md (обязательные условия задачи) ==='
      git show "$HEAD_SHA:docs/case.md" 2>/dev/null || echo "(docs/case.md ещё нет)"
      echo
      echo '=== коммиты за интервал ==='
      git log --oneline "$RANGE" 2>/dev/null || echo "(нет)"
      echo
      echo '=== diffstat ==='
      git diff --stat "$RANGE" 2>/dev/null
      echo
      echo "=== diff (обрезан до $MAX_DIFF_LINES строк) ==="
      git diff "$RANGE" 2>/dev/null | head -n "$MAX_DIFF_LINES"
    } > "$CTX"

    printf '## %s — %s\n\n<!-- вставьте сюда ответ агента целиком, затем: scripts/ops/audit.sh save %s -->\n' \
      "$NOW" "$HEAD_SHA" "$TS" > "$WT/reports/audit-$TS.md"
    echo "$HEAD_SHA" > "$STATE"

    echo
    echo "контекст собран: $CTX  ($(wc -l < "$CTX") строк)"
    echo "в буфер обмена:  cat \"$CTX\" | clip"
    echo "ответ вставить в: $WT/reports/audit-$TS.md"
    echo "затем:            scripts/ops/audit.sh save $TS"
    ;;

  save)
    TS=$TS_ARG
    F="$WT/reports/audit-$TS.md"
    [ -f "$F" ] || { echo "нет $F" >&2; exit 1; }
    if grep -q "вставьте сюда ответ агента" "$F"; then
      echo "в $F ещё заглушка — вставьте ответ агента и повторите" >&2; exit 1
    fi
    git -C "$WT" add -- "reports/audit-$TS.md"
    git -C "$WT" commit -q -m "ops: аудит $TS" -- "reports/audit-$TS.md" \
      && echo "закоммичено: reports/audit-$TS.md" || echo "нечего коммитить"
    [ "${AUDIT_PUSH:-0}" = "1" ] && { git -C "$WT" push -q origin ops/audit && echo "отправлено"; }
    ;;

  list)
    echo "собранные контексты:"; ls -1 "$WT/context" 2>/dev/null || echo "  нет"
    echo "отчёты:"
    for f in "$WT"/reports/audit-*.md; do
      [ -f "$f" ] || continue
      if grep -q "вставьте сюда ответ агента" "$f"; then echo "  НЕ ЗАПОЛНЕН  $(basename "$f")"
      else echo "  готов        $(basename "$f")"; fi
    done
    ;;

  *) echo "usage: $0 prep|save <HHMM>|list" >&2; exit 1 ;;
esac
