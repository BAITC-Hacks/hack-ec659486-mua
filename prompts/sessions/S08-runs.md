# S08 — Оркестратор и API запусков (волна 2, 14:40–15:20, A, ветка `s/runs`)

Прочитай `AGENTS.md`, `docs/case.md` (условие 4 — источник у каждого вывода), `docs/spec-case11.md` §2, §3, §4 целиком. Модели и заглушки роутера — из S01 (`backend/app/schemas.py`, `backend/app/routers/runs.py`, `backend/app/store.py`; если их нет в твоей ветке — `git fetch origin s/contract && git show origin/s/contract:<путь>`). Сигнатуры соседей: S04 `app.parse.docx.parse_docx(path, version, name=None) -> Document`, S05 `app.units.detect_units(doc_before, doc_after) -> list[UnitChange]`; для `app.functions`, `app.matching`, `app.duplicates`, `app.conclusion` возьми имена из spec §2 (`extract_functions`, `match_functions`, `find_duplicates`, `find_conflicts`, `write_conclusion`) и ищи их через `getattr`.

**Пишешь только в:** `backend/app/pipeline.py`, `backend/app/store.py`, `backend/app/routers/runs.py`, `backend/tests/test_runs.py`.
**Не трогаешь:** `main.py`, `schemas.py`, `llm.py`, `prebuilt/*`, модули шагов, фронт, чужие тесты. Новых зависимостей нет.

Задача: связать шаги в один фоновой прогон, который доходит до `done` на тестовом комплекте в mock-режиме, даже когда часть модулей ещё не влилась, и отдать всё это по API из spec §4.

Сделай:
1. `store.py`: in-memory dict + JSON-дамп в `backend/data/runs/{run_id}.json` (`put`/`get`/`update_status`; каталог создавать сам, путь относительно `backend/`, каждая запись дампится целиком). При старте приложения дампы читать не нужно — `get` неизвестного id → `None`.
2. `pipeline.py`: `async def run_pipeline(run_id)` — шаги `parsing → units → functions → matching → conclusion → done`, статус и `progress` (10/30/50/70/90/100) обновляются в store перед каждым шагом. Каждый шаг — обёртка `_step(name, fn)`: модуль импортируется лениво внутри шага; `ImportError`/`AttributeError` → шаг пропущен, в `stats["skipped"]` запись `{"step", "reason": "модуль app.units ещё не реализован"}`, прогон продолжается с пустым результатом этого шага; любое другое исключение → статус `error`, `error` — понятный русский текст (в mock без фикстуры: «нет фикстуры <файл>, для своих документов нужен ключ OpenAI в .env»), процесс не падает. Синхронные функции шагов — через `asyncio.to_thread`. Результат — `Report` из `schemas.py`; `conclusion_md` при пропуске P6 — честная строка «заключение не сформировано: модуль не реализован», без выдуманных находок; `stats` — счётчики по статусам.
3. `routers/runs.py`: `POST /api/runs` (multipart `before[]`, `after[]`; проверка расширения `.docx`, ≤ 10 файлов суммарно, ≤ 10 МБ каждый, обе группы непустые; иначе `400 {error, detail}` по-русски; файлы сохраняются в `backend/data/runs/{run_id}/`), `POST /api/runs/demo` (редакции 8 и 9 из `data/case11/`), `GET /api/runs/{id}` (`RunStatus`), `.../report` (404 пока не `done`, с текстом «отчёт ещё не готов»), `.../clauses/{doc_id}/{clause_number}`, `.../report.md` (`text/markdown`, `conclusion_md`). Запуск — `asyncio.create_task(run_pipeline(run_id))`.
4. `tests/test_runs.py` (TestClient, `LLM_MODE=mock`): demo-run доходит до `done` — дождись через `GET` статуса с таймаутом 60 с; отчёт валиден по `Report`; у каждой находки в отчёте непустые `sources`; `report.md` отдаёт markdown; `POST /api/runs` с `.pdf` → 400 с «не поддержан»; пропущенный модуль виден в `stats["skipped"]`, а не молча. Если `app.parse` тоже отсутствует — тест всё равно зелёный: отчёт пустой, но валидный, статус `done`.

**Done-when:** `cd backend && LLM_MODE=mock uv run pytest -q tests/test_runs.py`
**Cut-if:** `clauses/...` отдаёт 404 с текстом «панель источника — S12»; multipart-загрузка валидирует только расширение.

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/runs`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S08): <что сделано>" && git push -u origin s/runs`.
Затем создай `status/agents/S08.md` в этом worktree: первая строка `# S08 — ЗЕЛЕНО` или `# S08 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
