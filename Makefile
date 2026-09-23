# Каркас хакатона: единые команды для backend (uv) и frontend (npm).
# Все цели phony, потому что рядом лежат каталоги backend/ и frontend/.

.PHONY: help dev down backend frontend install test lint typecheck fmt build check

help: ## Список команд
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

.env:
	cp .env.example .env
	@echo ">> Создан .env из .env.example (ключ OpenAI можно не указывать: будет mock-режим)"

dev: .env ## Поднять всё в Docker (backend :8000, frontend :3000)
	docker compose up --build

down: ## Остановить и удалить контейнеры
	docker compose down

backend: ## Backend локально с автоперезагрузкой (нужен uv)
	cd backend && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

frontend: ## Frontend локально (нужен Node >= 20)
	cd frontend && npm run dev

install: ## Установить зависимости (uv sync + npm install)
	cd backend && uv sync
	cd frontend && npm install

test: ## Тесты backend (pytest, mock-режим)
	cd backend && LLM_MODE=mock uv run pytest -q

lint: ## Линтеры (ruff + eslint)
	cd backend && uv run ruff check .
	cd frontend && npm run lint

typecheck: ## Проверка типов frontend (tsc --noEmit)
	cd frontend && npm run typecheck

fmt: ## Автоформатирование backend (ruff)
	cd backend && uv run ruff format . && uv run ruff check --fix .

build: ## Production-сборка frontend (next build)
	cd frontend && npm run build

check: ## Всё сразу: ruff + pytest + eslint + tsc + build. Без make: scripts/check.sh
	scripts/check.sh

deploy: ## Деплой на VPS: make deploy HOST=root@IP (см. deploy/)
	@test -n "$(HOST)" || (echo "usage: make deploy HOST=root@IP" && exit 1)
	deploy/deploy.sh $(HOST)

smoke: ## Docker smoke test: build, start, hit /health, /api/example, frontend
	deploy/smoke.sh

# Всё остальное — обычные скрипты, make для них не нужен и на Windows его нет:
#   scripts/check.sh                       полная проверка
#   scripts/checkin.sh A "done" "doing"    чекин часа
#   scripts/ops/new-session.sh s/parser    поднять сессию
#   scripts/ops/merge-train.sh "s/a s/b"   мерж-поезд
#   scripts/ops/init-ops-branch.sh         ветка ops/audit
#   scripts/ops/audit.sh prep | save HHMM  аудит S21
#   scripts/ops/admission-check.sh <url>   прогон допуска S22
#   deploy/smoke.sh                        docker smoke
#   git config core.hooksPath scripts/hooks   хуки
