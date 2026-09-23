# S09 — Извлечение функций по пунктам (волна 3, 15:20–16:00, A, ветка `s/functions`)

Прочитай `AGENTS.md`, `docs/case.md` (условия 2–4 опираются на твой шаг), `docs/spec-case11.md` §2 P3, §3, §5; `backend/app/llm.py` (`LLM`, `complete_json`, `strict_schema`, `LLMError`, `llm.mode`); `backend/app/prebuilt/lib_normalize.py` (`signature`); модели `Document`, `Clause` (с `section_path`, `lead_in`, `modality`), `Source`, `Unit`, `Function` (с `executor`, `modality`, `context_clause_numbers`) из `backend/app/schemas.py`; `backend/app/units.py` из `origin/s/units` (фикстуры по хэшу — как там).

**Пишешь только в:** `backend/app/functions.py`, `backend/app/prompts/extract_functions.md`, `backend/app/mocks/extract_functions/**`, `backend/tests/test_functions.py`.
**Не трогаешь:** `main.py`, `schemas.py`, `llm.py`, `llm_schemas.py`, `units.py`, `prebuilt/`, `routers/`, `pipeline.py`, фронт.

Задача: `extract_functions(doc: Document, unit: Unit | None, llm: LLM) -> tuple[list[Function], list[Function]]` — `(functions, constraints)`: атомарные функции с исполнителем, модальностью, категорией, сигнатурой, пунктом-источником и пунктами контекста; запреты — отдельным списком ограничений; `extract_all(doc, units, llm) -> tuple[list[Function], list[Function]]` для документа целиком. Функции идут в поиск кандидатов и проверку (S10), ограничения — только в отчёт (список «Ограничения») и в правила конфликтов (S11). Сигнатура — только кандидат для поиска, не решение.

Сделай:
1. Выбор пунктов: для `unit` — пункты, где встречается название или аббревиатура подразделения (нормализация как в S05), плюс пункты из `unit.sources`. Если `units` пуст или пунктов никому не досталось — функции всего документа: разделы 2 («Цели, задачи и функции») и 5 («Права и обязанности»), `unit_id` = id корневого подразделения (БВА) или `""`. Пункты без номера и заголовки разделов не передавать. Каждый пункт передаётся с контекстом из `Clause`: `section_path` (цепочка заголовков/номеров родителей) и `lead_in` (вводная фраза родительского пункта, например «БВА не имеет права:» или «Главный аудитор:»).
2. `prompts/extract_functions.md` (system, по-русски): один пункт → одна или несколько атомарных функций; текст — короткая формулировка из пункта без пересказа; для каждой — `executor` (кто выполняет: подразделение или должность — из `lead_in`, `section_path` или текста пункта; иначе `null`), `modality` ∈ duty|right|prohibition|neutral (из `lead_in` и текста: «не вправе», «не имеет права», «запрещается», «не допускается» → prohibition; «имеет право», «вправе» → right; «осуществляет», «обеспечивает», «проводит», «формирует», «представляет», «обязан» → duty; иначе neutral); `category` ∈ task|function|right|duty|responsibility (по-русски в промпте: задача / функция / право / обязанность / ответственность; раздел 2.3 — task, 2.4 — function, 5.x — right/duty по глаголу); `clause_number` только из переданного списка; `context_clause_numbers` — номера родительских пунктов из `section_path`, тоже только из переданного списка; ничего не додумывать. User — JSON `{version, unit, clauses:[{number, text, section_path, lead_in}]}`.
3. Схема: `ExtractFunctionsOut {functions:[{text, category, executor: str|None, modality, clause_number, context_clause_numbers: list[str]}]}` ровно по spec §5 (из `llm_schemas.py`, если S13 уже влит, иначе своя pydantic-модель с `extra="forbid"`), `category` и `modality` — Literal, через `strict_schema`. Ответ проверяй кодом: `clause_number` не из переданного множества или пустой `text` — запись отбрасывается с `logger.warning`; чужие номера в `context_clause_numbers` выбрасываются; ошибка схемы — `LLMError`, не пустой список молча. Модальность перепроверяй кодом по `lead_in` и тексту пункта (правила из п. 2): если код видит запрет, а модель — нет, побеждает код. Записи с `modality == prohibition` — не функции: они уходят в `constraints`, а не в `functions`.
4. `Function`: `id = sha1(doc.id + clause_number + text)[:12]`, `signature = lib_normalize.signature(text)`, `executor`, `modality`, `context_clause_numbers` = валидные номера от модели, дополненные кодом номерами родительских пунктов из `section_path` (те, что есть в документе), `sources = [Source(doc_id, doc_name, version, clause_number, quote=текст пункта дословно)]`. Если `executor` от модели пуст, а `lead_in` называет подразделение или должность — подставь его кодом.
5. Кэш и mock: `hash = sha256(json.dumps(user_payload, ensure_ascii=False, sort_keys=True))[:16]`. Live — результат в памяти по хэшу (повторный вызов без LLM). Mock — читай `mocks/extract_functions/<hash>.json`; нет файла — `LLMError` с именем ожидаемого файла. Для стабильного хэша пункты в payload сортируй по `index`.
6. Фикстуры для тестового комплекта (`data/case11/*.txt` — те же docx текстом): редакции 8 и 9, функции из разделов 2 и 5, формат — как живой ответ модели (S15 заменит реальными без правки кода), с `executor`, `modality`, `context_clause_numbers`. Минимум по 15 функций на редакцию, обязательно 2.4.2, 2.4.9, 2.4.10, 5.1.1, 5.1.4; обязательно хотя бы один пункт под вводной «не имеет права:» с `modality = prohibition`.
7. `tests/test_functions.py` (Document строй из txt сам, как S05): на комплекте ≥ 15 функций у каждой редакции, у каждой непустые `sources` и `signature`, номер пункта есть в документе, `quote` равен тексту пункта; пункт под «не имеет права:» не попадает в `functions`, попадает в `constraints` с `modality == "prohibition"`; у функции под вводной «Главный аудитор:» (или названием подразделения) `executor` заполнен из `lead_in`; чужой `clause_number` в фикстуре → запись отброшена; нет фикстуры → `LLMError`; повторный вызов не обращается к `LLM` (счётчик через monkeypatch).

**Done-when:** `cd backend && LLM_MODE=mock uv run pytest -q tests/test_functions.py`
**Cut-if:** категория только task|function|duty; `context_clause_numbers` заполняются только кодом из `section_path`; привязка к подразделению не делается — все функции документа с `unit_id=""`, честно отмечено в `note` статуса. Разделение на `functions`/`constraints` по модальности и `executor` из `lead_in` не режутся.

В конце выведи список изменённых файлов и вывод Done-when.


## Дополнение по аудиту: единый контракт

- `category` — только значения из `schemas.py` (английский enum), перевод на русский — во фронте. Отсутствующие значения — `None`, не пустая строка.
- Наследование контекста обязательно: функция получает исполнителя из ближайшего `lead_in`/заголовка (например «Директоры департаментов и Директоры направлений ДИТААД и ДОА:» → executor для всех подпунктов), а пункты под «не имеют права:» — в `constraints`, не в `functions`.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/functions`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S09): <что сделано>" && git push -u origin s/functions`.
Затем создай `status/agents/S09.md` в этом worktree: первая строка `# S09 — ЗЕЛЕНО` или `# S09 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
