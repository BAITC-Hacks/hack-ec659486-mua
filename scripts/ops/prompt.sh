#!/usr/bin/env bash
# Положить промпт в буфер обмена для вставки в GUI (Codex app / Claude Code).
# Usage: scripts/ops/prompt.sh S04         -> prompts/sessions/S04-*.md
#        scripts/ops/prompt.sh timekeeper  -> prompts/timekeeper.md
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
KEY=${1:?S04 | timekeeper | audit | имя файла в prompts/}
if [ -f "prompts/sessions/$KEY" ]; then F="prompts/sessions/$KEY"
elif ls prompts/sessions/${KEY}-*.md >/dev/null 2>&1; then F=$(ls prompts/sessions/${KEY}-*.md | head -1)
elif [ -f "prompts/$KEY.md" ]; then F="prompts/$KEY.md"
elif [ -f "prompts/ops_$KEY.md" ]; then F="prompts/ops_$KEY.md"
else echo "не нашёл промпт для $KEY" >&2; exit 1; fi
if command -v xclip >/dev/null; then xclip -selection clipboard < "$F"; echo "в буфере: $F ($(wc -w < "$F") слов)"; else echo "xclip нет — открой файл: $F"; fi
