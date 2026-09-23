#!/usr/bin/env bash
# Полная проверка без make: ruff, pytest, eslint, tsc, next build.
# make на Windows без WSL нет, поэтому это основная команда, а `make check` —
# просто обёртка над ней.
#
# Usage: scripts/check.sh [backend|frontend]
set -euo pipefail
cd "$(dirname "$0")/.."
PART=${1:-all}

fail() { echo; echo "ПРОВЕРКА НЕ ПРОШЛА: $*" >&2; exit 1; }

if [ "$PART" = "all" ] || [ "$PART" = "backend" ]; then
  echo "== ruff"
  (cd backend && uv run ruff check .) || fail "ruff"
  echo "== pytest (mock-режим)"
  (cd backend && LLM_MODE=mock uv run pytest -q) || fail "pytest"
fi

if [ "$PART" = "all" ] || [ "$PART" = "frontend" ]; then
  echo "== eslint"
  (cd frontend && npm run lint) || fail "eslint"
  echo "== tsc --noEmit"
  (cd frontend && npm run typecheck) || fail "tsc"
  echo "== next build"
  (cd frontend && npm run build) || fail "next build"
fi

echo
echo ">> проверка пройдена"
