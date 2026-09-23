# S08 — Оркестратор и API запусков (волна 2, 14:40–15:20, A, ветка `s/runs`)

Прочитай `AGENTS.md`, `docs/case.md` (условие 4 — источник у каждого вывода), `docs/spec-case11.md` §2 (в том числе §2а — почему кандидаты и проверка разделены), §3, §4 целиком. Модели и заглушки роутера — из S01 (`backend/app/schemas.py`, `backend/app/routers/runs.py`, `backend/app/store.py`; если их нет в твоей ветке — `git fetch origin s/contract && git show origin/s/contract:<путь>`). Сигнатуры соседей: S04 `app.parse.docx.parse_docx(path, version, name=None) -> Document`, S05 `app.units.detect_units(doc_before, doc_after) -> list[UnitChange]`; для `app.functions` (`extract_functions`), `app.candidates` (`find_candidates`, `find_duplicate_candidates`), `app.matching` (`verify_matches(before, after, candidates, llm, after_clauses)`, `confirm_loss`), `app.duplicates` (`find_duplicates(functions_by_unit, llm, candidate_pairs)` — внутри LLM-вызов `verify_duplicates`), `app.rules.conflicts` (`find_conflicts(functions_by_unit, llm, constraints)` — внутри `explain_conflict`), `app.conclusion` (`build_facts`, `write_conclusion`), `app.export_md` (`export_markdown`) — ищи их через `getattr` — сигнатуры соседей могут отличаться, поэтому ориентируйся на модели §3 (`FunctionMatch` со списками `before`/`after`, `verified`, `verification`; `Report.constraints`; `Report.stats.unverified_candidates`).

**Пишешь только в:** `backend/app/pipeline.py`, `backend/app/store.py`, `backend/app/routers/runs.py`, `backend/tests/test_runs.py`.
**Не трогаешь:** `main.py`, `schemas.py`, `llm.py`, `prebuilt/*`, модули шагов, фронт, чужие тесты. Новых зависимостей нет.

Задача: связать шаги в один фоновой прогон, который доходит до `done` на тестовом комплекте в mock-режиме, даже когда часть модулей ещё не влилась, и отдать всё это по API из spec §4.

Сделай:
1. `store.py`: in-memory dict + JSON-дамп в `backend/data/runs/{run_id}.json` (`put`/`get`/`update_status`; каталог создавать сам, путь относительно `backend/`, каждая запись дампится целиком). При старте приложения дампы читать не нужно — `get` неизвестного id → `None`.
2. `pipeline.py`: `async def run_pipeline(run_id)` — шаги `parsing → units → functions → candidates → verification → conflicts → conclusion → done (или partial/error)` (ровно те статусы, что в spec §4: `queued|parsing|units|functions|candidates|verification|conflicts|conclusion|done|partial|error`), `progress` 5/15/30/45/65/80/90/100 обновляется в store перед каждым шагом. Каждый шаг — обёртка `_step(name, fn)`: модуль импортируется лениво внутри шага (`app.parse.docx`, `app.units`, `app.functions`, `app.candidates`, `app.matching`, `app.duplicates`, `app.rules.conflicts`, `app.conclusion`/`app.export_md`); `ImportError`/`AttributeError` → шаг пропущен, в `stats["skipped"]` запись `{"step", "reason": "модуль app.candidates ещё не реализован"}`, прогон продолжается с пустым результатом этого шага; любое другое исключение → статус `error`, `error` — понятный русский текст (в mock без фикстуры: «нет фикстуры <файл>, для своих документов нужен ключ OpenAI в .env»), процесс не падает. Синхронные функции шагов — через `asyncio.to_thread`. Содержание шагов:
   - `functions`: `extract_functions` по обеим версиям; функции с `modality = prohibition` отделяются в `Report.constraints` и дальше в `candidates`/`verification` не идут (в `conflicts` передаются).
   - `candidates`: `app.candidates` — гибридный поиск (лексический + сигнатура + опционально dense + RRF) кандидатов «после» для каждой функции «до» и кандидатов дублей между функциями разных подразделений одной версии. Это только кандидаты, статусов на этом шаге нет.
   - `verification`: `app.matching.verify_matches` (LLM, решение по каждой функции «до» с её кандидатами → `FunctionMatch` со списками `before`/`after`, `kind`, `status`, `verified`, `verification`), при `none` — `confirm_loss` по всему документу «после» (внутри `verify_matches`, ей передаются пункты «после»); `app.duplicates.find_duplicates(functions_by_unit, llm, candidate_pairs)` для кандидатов дублей из шага `candidates` (внутри LLM `verify_duplicates`). Всё, что не получило решения проверки (нет ответа, лимит пакета, низкая уверенность), остаётся в отчёте с `verified = false` и `note` с причиной — не выдумывать `lost`; если `app.candidates` пропущен, `verification` тоже пропускается с записью в `skipped`, а все функции остаются непроверенными кандидатами.
   - `conflicts`: `app.rules.conflicts.find_conflicts` по функциям «после» с учётом `constraints` (внутри — `explain_conflict`).
   - `conclusion`: `write_conclusion` только из фактов предыдущих шагов, затем `export_md`.
   Результат — `Report` из `schemas.py`; `conclusion_md` при пропуске P6 — честная строка «заключение не сформировано: модуль не реализован», без выдуманных находок; `stats` — счётчики по статусам подразделений и функций (`kept`, `changed`, `lost`, `new`, `moved`), `duplicates`, `conflicts` и обязательно `unverified_candidates` — число находок с `verified = false` среди `function_matches`, `duplicates` и `conflicts` (в mock без модулей проверки — все функции «до»). В отчёт попадают только находки с непустыми `sources`; находка без источника отбрасывается с `logger.warning`, не подставляется.
3. `routers/runs.py`: `POST /api/runs` (multipart `before[]`, `after[]`; проверка расширения `.docx`, ≤ 10 файлов суммарно, ≤ 10 МБ каждый, обе группы непустые; иначе `400 {error, detail}` по-русски; файлы сохраняются в `backend/data/runs/{run_id}/`), `POST /api/runs/demo` (редакции 8 и 9 из `data/case11/`), `GET /api/runs/{id}` (`RunStatus`), `.../report` (404 пока не `done`, с текстом «отчёт ещё не готов»), `.../clauses/{doc_id}/{clause_number}`, `.../report.md` (`text/markdown`, `conclusion_md`). Запуск — `asyncio.create_task(run_pipeline(run_id))`.
4. `tests/test_runs.py` (TestClient, `LLM_MODE=mock`): demo-run доходит до `done` — дождись через `GET` статуса с таймаутом 60 с, по пути статусы только из перечня spec §4 (проверь хотя бы, что встретился `candidates` или `verification` либо они в `stats["skipped"]`); отчёт валиден по `Report`; у каждой находки в отчёте непустые `sources`; в `stats` есть ключ `unverified_candidates` и он равен числу находок с `verified = false` среди `function_matches`, `duplicates`, `conflicts`; в `function_matches` нет функций с `modality = prohibition` (они в `constraints`); `report.md` отдаёт markdown; `POST /api/runs` с `.pdf` → 400 с «не поддержан»; пропущенный модуль виден в `stats["skipped"]`, а не молча. Если `app.parse` тоже отсутствует — тест всё равно зелёный: отчёт пустой, но валидный, статус `done`.

**Done-when:** `cd backend && LLM_MODE=mock uv run pytest -q tests/test_runs.py`
**Cut-if:** `clauses/...` отдаёт 404 с текстом «панель источника — S12»; multipart-загрузка валидирует только расширение.

В конце выведи список изменённых файлов и вывод Done-when.


## Дополнение по аудиту: статусы и честность прогона

- Статусы run: `done` только если все обязательные шаги (parsing, units, functions, candidates, verification, conflicts, conclusion) выполнены; если модуль отсутствует или шаг упал — `partial` с полем `missing_steps` и понятным `detail`; необработанное исключение — `error`. Пустой результат и невыполненный анализ — разные состояния: «изменений не найдено» допустимо только при `done`.
- `ImportError` внутри модуля (не «модуль отсутствует», а сломанная зависимость) — это `error`, не пропуск.
- Тест: при отсутствии модулей demo-run завершается `partial`, отчёт валиден, `missing_steps` непуст; при наличии всех модулей — `done`.
- Загрузка: лимит 10 файлов суммарно на обе зоны; неподдерживаемый формат → 422 `{error, detail}` (единый статус со всеми сессиями).
- Тестовый комплект читается из `settings.data_dir/case11` (в Docker `/app/data`, локально `../data`), дампы — в `settings.runtime_dir`.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/runs`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S08): <что сделано>" && git push -u origin s/runs`.
Затем создай `status/agents/S08.md` в этом worktree: первая строка `# S08 — ЗЕЛЕНО` или `# S08 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
