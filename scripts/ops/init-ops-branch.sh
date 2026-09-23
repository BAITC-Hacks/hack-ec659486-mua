#!/usr/bin/env bash
# Создаёт orphan-ветку ops/audit и worktree для неё.
#
# Почему orphan: у ветки свой корень и своё дерево, в ней нет ни одного файла проекта.
# Конфликтовать с main ей нечем, мержить её некуда. Всё остаётся в репозитории команды,
# как требует Положение 5.4.11, но не смешивается с кодом.
#
# Usage: scripts/ops/init-ops-branch.sh [worktree_path]     (default: ../wt-ops)
set -euo pipefail
WT=${1:-../wt-ops}
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if git show-ref --verify --quiet refs/heads/ops/audit; then
  echo "ветка ops/audit уже есть"
else
  echo "== создаю orphan-ветку ops/audit"
  TMP=$(mktemp -d)
  git worktree add --detach "$TMP" >/dev/null
  (
    cd "$TMP"
    git checkout --orphan ops/audit
    git rm -rq --cached . 2>/dev/null || true
    find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
    mkdir -p reports
    cat > README.md <<'EOF'
# Операционные отчёты

Orphan-ветка. Здесь нет кода проекта и никогда не будет: только отчёты фоновых сессий.
В `main` не мержится.

- `reports/audit-*.md` — S8, аудит diff каждые 30 минут
- `reports/admission-*.md` — S9, прогон допуска по README в чистом клоне

Смысл S9: Положение 5.4.16 и 5.6.5 — если итоговую версию не удаётся запустить по инструкциям
из репозитория, команда не допускается к дальнейшему отбору, пояснения и исправления
не принимаются. Проверяем это каждые полчаса, а не 24 сентября.
EOF
    touch reports/.gitkeep
    git add -A
    git commit -qm "ops: orphan-ветка для отчётов фоновых сессий"
  )
  git worktree remove --force "$TMP"
  rm -rf "$TMP"
fi

if [ -d "$WT" ]; then
  echo "worktree $WT уже существует"
else
  git worktree add "$WT" ops/audit
fi
echo
echo "готово: $WT на ветке ops/audit"
echo "дальше: scripts/ops/audit.sh prep (S21) и ADMISSION_LOOP=1 scripts/ops/admission-check.sh <url> (S22)"
