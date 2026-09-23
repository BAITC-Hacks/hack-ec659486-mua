#!/usr/bin/env bash
# Поднять пишущую сессию: worktree + ветка от main.
#
# Каждая сессия живёт в своём worktree, чтобы параллельные агенты не топтали
# рабочую копию друг друга. Ветка всегда от main, а не от чужой ветки:
# иначе мерж-поезд превращается в дерево.
#
# Агенты запускаются только в интерфейсе: скрипт готовит каталог, дальше вы открываете
# новую сессию в приложении агента и указываете этот путь рабочим каталогом.
#
# Usage: scripts/ops/new-session.sh s/parser [codex|claude|antigravity] [путь_worktree]
set -euo pipefail
BR=${1:?имя ветки, например s/parser}
TOOL=${2:-codex}
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
WT=${3:-../wt-$(basename "$BR")}

# BASE_REF=origin/prep/laptop-setup — для репетиции в dev-репо, где main не содержит каркас
BASE_REF=${BASE_REF:-origin/main}
git fetch -q origin "${BASE_REF#origin/}" 2>/dev/null || echo "fetch не прошёл, беру локальную ссылку"
BASE=$(git rev-parse --verify -q "$BASE_REF" || git rev-parse --verify -q "${BASE_REF#origin/}" || git rev-parse main)

if git show-ref --verify --quiet "refs/heads/$BR"; then
  echo "ветка $BR уже есть"
else
  git branch "$BR" "$BASE"
fi
[ -d "$WT" ] || git worktree add "$WT" "$BR"

# Маркер для хука prepare-commit-msg: при запуске из интерфейса переменной окружения нет,
# поэтому имя инструмента лежит рядом с кодом. Файл в .gitignore.
printf 'branch=%s\ntool=%s\n' "$BR" "$TOOL" > "$WT/.session"

cat <<EOF

сессия поднята
  ветка:      $BR  (от $(git rev-parse --short "$BASE"))
  worktree:   $WT
  инструмент: $TOOL

Откройте новую сессию в интерфейсе агента и укажите рабочим каталогом путь worktree выше.
Промпт положить в буфер: cat prompts/sessions/<файл>.md | clip

Напоминание:
  - пиши только в файлы своей строки матрицы владения (docs/sessions.md);
  - backend/app/main.py и frontend/app/layout.tsx не трогает никто после волны 1;
  - сессия закрыта, когда зелёная её команда Done-when, а не когда «выглядит готово»;
  - мерж делает B через merge-train, сама сессия в main не пушит.
EOF
