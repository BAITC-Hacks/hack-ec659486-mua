#!/usr/bin/env bash
# Чекин за 10 секунд из любого worktree: дописывает строку в status/log-<WHO>.md
# в основном worktree и коммитит ТОЛЬКО этот файл.
#
# Почасовой результат теперь прямо назван основанием для дисквалификации
# (Положение 5.9.2, состав результата — 5.4.8), поэтому строка должна реально попасть в репозиторий.
#
# Два правила, ради которых скрипт выглядит именно так:
#   1. `git commit` без pathspec коммитит весь уже заполненный index, включая чужие
#      подготовленные файлы. Поэтому здесь всегда `git commit -- <путь>`.
#   2. Автоматический pull --rebase из скрипта гоняется с ручным мержем второго человека.
#      Поэтому push по умолчанию выключен: интегратор один (B) и он пушит осознанно.
#      Включить разово: CHECKIN_PUSH=1 scripts/checkin.sh ...
#
# Usage: scripts/checkin.sh WHO "done" "doing" ["blocker"] ["eta"]
#   или: scripts/checkin.sh WHO=A DONE="..." DOING="..." BLOCK="-" ETA=14:20
set -euo pipefail
WHO=${1:?who (A/B)}; DONE=${2:?done}; DOING=${3:?doing}; BLOCK=${4:--}; ETA=${5:--}

# Ищем worktree с main. substr вместо $2: путь может содержать пробелы.
MAIN=$(git worktree list --porcelain | awk '/^worktree /{p=substr($0,10)} /^branch refs\/heads\/main$/{print p; exit}')
if [ -z "${MAIN:-}" ]; then
  MAIN=$(git rev-parse --show-toplevel)
  echo "!! ветка main нигде не выгружена: пишу в $(git branch --show-current) в $MAIN" >&2
  echo "!! перед сдачей убедиться, что чекины попали в main" >&2
fi

TS=$(date +%H:%M)
SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "-")
BR=$(git branch --show-current 2>/dev/null || echo "-")
REL="status/log-$WHO.md"
LOG="$MAIN/$REL"

mkdir -p "$MAIN/status"
[ -f "$LOG" ] || printf '| Время | Кто | Сделано | Делаю | Блокер | ETA | Ветка@коммит |\n|---|---|---|---|---|---|---|\n' > "$LOG"
printf '| %s | %s | done: %s | doing: %s | block: %s | eta: %s | %s@%s |\n' \
  "$TS" "$WHO" "$DONE" "$DOING" "$BLOCK" "$ETA" "$BR" "$SHA" >> "$LOG"
tail -1 "$LOG"

git -C "$MAIN" add -- "$REL"
git -C "$MAIN" commit -q -m "status: checkin $WHO $TS" -- "$REL" || true

if [ "${CHECKIN_PUSH:-0}" = "1" ]; then
  git -C "$MAIN" push -q origin main && echo "pushed" || echo "push не прошёл — сделайте fetch+merge вручную"
else
  echo "коммит локальный. Отправить: git -C \"$MAIN\" push origin main"
fi
