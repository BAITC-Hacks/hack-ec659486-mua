#!/usr/bin/env bash
# Мерж-поезд: мержит ветки сессий в main по порядку и проверяет после каждой.
#
# Порядок не случайный: бэкенд-данные -> бэкенд-модель -> бэкенд-роутеры ->
# фронт-компоненты -> фронт-страницы -> тесты -> доки. Так поздние ветки видят
# уже смерженные зависимости, а не наоборот.
#
# Ветка, после которой проверка красная, откатывается из поезда и едет следующим
# рейсом. Чинить в main на хакатоне нельзя: сломанный main блокирует обоих.
#
# Usage: scripts/ops/merge-train.sh "s/parser s/features s/api-stub"
#   CHECK="cd backend && uv run pytest -q"   — своя команда проверки (по умолчанию make check)
#   TRAIN_PUSH=1                             — пушить main после успешного рейса
set -uo pipefail
BRANCHES=${1:?список веток через пробел, например "s/parser s/features"}
CHECK=${CHECK:-make check}
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"

CUR=$(git branch --show-current)
[ "$CUR" = "main" ] || { echo "мерж-поезд запускается из main, сейчас $CUR" >&2; exit 1; }
[ -z "$(git status --porcelain)" ] || { echo "рабочая копия не чиста — сначала коммит" >&2; exit 1; }

MERGED=""; SKIPPED=""
for BR in $BRANCHES; do
  echo
  echo "===== $BR ====="
  # Ветка второго человека приезжает через fetch и лежит в refs/remotes/origin/,
  # локальной копии у интегратора нет. Проверять только refs/heads — значит молча
  # пропускать всё, что сделал напарник.
  git fetch -q origin "$BR" 2>/dev/null || true
  REF=""
  LOCAL_OK=$(git show-ref --verify --quiet "refs/heads/$BR" && echo 1 || echo 0)
  REMOTE_OK=$(git show-ref --verify --quiet "refs/remotes/origin/$BR" && echo 1 || echo 0)
  if [ "$REMOTE_OK" = "1" ] && [ "$LOCAL_OK" = "1" ]; then
    if git merge-base --is-ancestor "$BR" "origin/$BR"; then
      REF="origin/$BR"; echo "локальная $BR отстаёт — беру origin/$BR"
    else
      REF="$BR"
    fi
  elif [ "$REMOTE_OK" = "1" ]; then REF="origin/$BR"; echo "беру origin/$BR"
  elif [ "$LOCAL_OK" = "1" ]; then REF="$BR"
  else
    echo "!! ветки нет ни локально, ни на origin — пропускаю"; SKIPPED="$SKIPPED $BR(нет)"; continue
  fi
  BEFORE=$(git rev-parse HEAD)
  if ! git merge --no-ff -m "merge: $BR" "$REF"; then
    echo "!! конфликт — откатываю и снимаю ветку с рейса"
    git merge --abort || true
    SKIPPED="$SKIPPED $BR(конфликт)"; continue
  fi
  if eval "$CHECK"; then
    echo ">> $BR принят"
    MERGED="$MERGED $BR"
  else
    echo "!! проверка красная — откатываю $BR до $(git rev-parse --short "$BEFORE")"
    git reset --hard "$BEFORE"
    SKIPPED="$SKIPPED $BR(проверка)"
  fi
done

echo
echo "===== итог рейса ====="
echo "принято:  ${MERGED:- —}"
echo "снято:    ${SKIPPED:- —}"
if [ -n "$MERGED" ] && [ "${TRAIN_PUSH:-0}" = "1" ]; then
  git push origin main && echo "main отправлен"
elif [ -n "$MERGED" ]; then
  echo "отправить: git push origin main"
fi
[ -z "$SKIPPED" ] || echo "снятые ветки не чинятся в main — их владелец правит у себя и они едут следующим рейсом"
