# S01 — Контракт и «розетки» (волна 1, 14:15–14:40, A, ветка `s/contract`)

Прочитай `AGENTS.md`, `docs/case.md` (обязательные условия — приоритет), `docs/spec-case11.md` §3–§5 целиком.

**Пишешь только в:** `backend/app/schemas.py`, `backend/app/main.py`, `backend/app/routers/runs.py` (пустой роутер с заглушками),
`frontend/lib/types.ts`, `backend/tests/test_contract_smoke.py`.
**Не трогаешь:** остальное. Это фундамент: после тебя `main.py` и `schemas.py` никто не правит до волны 4.

Задача: зафиксировать контракт так, чтобы бэкенд-сессии и фронт-сессии писали параллельно и не встретились в одном файле.

Сделай:
1. `backend/app/schemas.py` — pydantic-модели ровно по spec §3: Document, Clause, Source, Unit, UnitChange, Function, FunctionMatch, Duplicate, Conflict, Report, RunStatus, RunCreated. Enum-статусы строками (Literal). Все поля обязательные, `additionalProperties` запрещены (`model_config = ConfigDict(extra="forbid")`).
2. `frontend/lib/types.ts` — те же типы 1:1 по именам полей.
3. `backend/app/routers/runs.py` — эндпоинты из spec §4 с заглушками, которые возвращают валидные по схемам объекты (`501`-ошибок нет: заглушка `POST /api/runs/demo` создаёт run со статусом `queued`, `GET /api/runs/{id}` отдаёт его, `GET .../report` отдаёт пустой Report с `stats`). Хранилище — простой dict в `backend/app/store.py` (создай, но только словарь + get/put; логику пайплайна не пиши).
4. `backend/app/main.py` — зарегистрируй роутер `runs` и оставь `/health`. Больше в main.py никто ничего не добавляет.
5. `backend/tests/test_contract_smoke.py` — TestClient: `/health`, `POST /api/runs/demo` → id, `GET /api/runs/{id}` валиден, `GET /api/runs/{id}/report` валиден по `Report`, `GET /docs` 200.

Не реализуй разбор, LLM и пайплайн — это S04–S14. Если в spec §3 чего-то не хватает для эндпоинтов §4 — добавь минимально и опиши в комментарии «добавлено S01».

**Done-when:** `cd backend && uv run pytest -q` зелёный, `/docs` показывает все эндпоинты из spec §4.
**Cut-if:** `GET .../clauses/...` и `report.md` можно оставить заглушками с пустым телом.

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/contract`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S01): <что сделано>" && git push -u origin s/contract`.
Затем создай `status/agents/S01.md` в этом worktree: первая строка `# S01 — ЗЕЛЕНО` или `# S01 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
