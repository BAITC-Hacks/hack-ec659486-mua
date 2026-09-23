# S01 — Контракт и «розетки» (волна 1, 14:15–14:40, A, ветка `s/contract`)

Прочитай `AGENTS.md`, `docs/case.md` (обязательные условия — приоритет), `docs/spec-case11.md` §3–§5 целиком.

**Пишешь только в:** `backend/app/schemas.py`, `backend/app/main.py`, `backend/app/routers/runs.py` (пустой роутер с заглушками),
`backend/app/store.py` (только dict + get/put), `frontend/lib/types.ts`, `backend/tests/test_contract_smoke.py`.
**Не трогаешь:** остальное. Это фундамент: после тебя `main.py`, `schemas.py` и `types.ts` никто не правит до конца дня; `routers/runs.py` и `store.py` в волне 2 перепишет S08.

Задача: зафиксировать контракт так, чтобы бэкенд-сессии и фронт-сессии писали параллельно и не встретились в одном файле.

Сделай:
1. `backend/app/schemas.py` — pydantic-модели ровно по spec §3: Document, Clause, Source, Unit, UnitChange, Function, FunctionMatch, Duplicate, Conflict, Report, RunStatus, RunCreated. Enum-статусы строками (Literal). Все поля обязательные, `additionalProperties` запрещены (`model_config = ConfigDict(extra="forbid")`). Обязательные поля контекста и проверки (в дополнение к spec §3, если там их нет — добавить с комментарием «добавлено S01»):
   - `Clause`: `section_path: list[str]` (цепочка заголовков/номеров родителей), `lead_in: str | None` (вводная фраза родительского пункта, например «БВА не имеет права:»), `modality: Literal["duty", "right", "prohibition", "neutral"]`.
   - `Function`: `executor: str | None` (кто выполняет — подразделение или должность), `modality` (тот же Literal), `context_clause_numbers: list[str]`. Запреты (`prohibition`) — ограничения, а не функции: в потери и дубли не идут, в отчёте показываются отдельным списком «Ограничения».
   - `FunctionMatch`: связи один-ко-многим — `before: list[Function]`, `after: list[Function]`, `kind: Literal["one_to_one", "split", "merge", "partial"]`, `status: Literal["kept", "changed", "lost", "new", "moved"]`, `verified: bool`, `verification: Literal["exact", "lexical", "llm"]`, `confidence: float`, `note: str`, `sources: list[Source]`.
   - `Duplicate`: `verified: bool`, `verification_note: str`, `verification`, `sources`.
   - `Conflict`: `role_pattern: str` (какое правило сработало), `severity`, `verified: bool`, `verification_note: str`, `verification`, источники обеих сторон.
   - `Report.stats`: помимо счётчиков — `unverified_candidates: int` (кандидаты в потери/дубли/конфликты без подтверждения, в UI помечаются «требует проверки»).
   Каждая находка несёт `sources` и `verification` (`exact|lexical|llm`); находка без источника не является выводом.
2. `frontend/lib/types.ts` — те же типы 1:1 по именам полей, включая `section_path`/`lead_in`/`modality` у `Clause`, `executor`/`modality`/`context_clause_numbers` у `Function`, `before[]`/`after[]`/`kind`/`verified`/`verification` у `FunctionMatch`, `verified`/`verification_note` у `Duplicate` и `Conflict`, `role_pattern` у `Conflict`, `stats.unverified_candidates` у `Report`. Union-типы строк вместо enum.
3. `backend/app/routers/runs.py` — эндпоинты из spec §4 с заглушками, которые возвращают валидные по схемам объекты (`501`-ошибок нет: заглушка `POST /api/runs/demo` создаёт run со статусом `queued`, `GET /api/runs/{id}` отдаёт его, `GET .../report` отдаёт пустой Report с `stats`). Хранилище — простой dict в `backend/app/store.py` (создай, но только словарь + get/put; логику пайплайна не пиши).
4. `backend/app/main.py` — зарегистрируй роутер `runs` и оставь `/health`. Больше в main.py никто ничего не добавляет.
5. `backend/tests/test_contract_smoke.py` — TestClient: `/health`, `POST /api/runs/demo` → id, `GET /api/runs/{id}` валиден, `GET /api/runs/{id}/report` валиден по `Report`, `GET /docs` 200.

Не реализуй разбор, LLM и пайплайн — это S04–S14. Если в spec §3 чего-то не хватает для эндпоинтов §4 — добавь минимально и опиши в комментарии «добавлено S01».

**Done-when:** `cd backend && uv run pytest -q` (smoke-тест проверяет и страницу /docs со всеми эндпоинтами spec §4).
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
