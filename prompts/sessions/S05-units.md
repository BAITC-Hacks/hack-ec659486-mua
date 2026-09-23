# S05 — Подразделения: извлечение и сопоставление (волна 2, 14:40–15:20, A, ветка `s/units`)

Прочитай `AGENTS.md`, `docs/case.md` (условие 1 — твоё), `docs/spec-case11.md` §2 P2, §3, §5; `backend/app/llm.py` (класс `LLM`, `complete_json`, `strict_schema`, mock-режим); модели `Document`, `Clause`, `Source`, `Unit`, `UnitChange` из `backend/app/schemas.py` (если ещё нет в `main` — `git fetch origin s/contract && git show origin/s/contract:backend/app/schemas.py`).

**Пишешь только в:** `backend/app/units.py`, `backend/app/prompts/extract_units.md`, `backend/app/prompts/match_units.md`, `backend/app/mocks/extract_units/**`, `backend/app/mocks/match_units/**`, `backend/tests/test_units.py`.
**Не трогаешь:** `main.py`, `schemas.py`, `llm.py`, `routers/`, `prebuilt/`, фронт.

Задача: `detect_units(doc_before: Document, doc_after: Document) -> list[UnitChange]` — какие подразделения сохранены / преобразованы / созданы / упразднены, каждое с пунктами-источниками.

Сделай:
1. Словарные кандидаты: по всем пунктам обеих версий ищи «департамент», «отдел», «управление», «служба», «блок», «сектор», «группа», «центр», ДЗО и аббревиатуры в скобках («(ДНМ)»). Кандидат = название + список `Clause`. Раздел «Структура» — пункты, чей `section` начинается с «3.» или содержит «Структура»; если раздела нет — весь документ.
2. `extract_units` через `LLM.complete_json(name, system, user, schema)`: system — текст `prompts/extract_units.md`, user — JSON `{version, clauses:[{number, text}]}`, schema — `strict_schema` pydantic-модели `{units:[{name, parent, clause_numbers}]}` (все поля обязательные, `parent` строка или `""`). Каждый `clause_number` проверяй по множеству номеров переданных пунктов; чужой номер отбрасывай, подразделение без единого валидного пункта — отбрасывай с `logger.warning`. Полученные `Unit` объединяй со словарными кандидатами по нормализованному названию (нижний регистр, без «(…)», ё→е, схлопнутые пробелы).
3. Сопоставление: одинаковое нормализованное название или аббревиатура → `kept` без LLM. Остаток — `match_units`: `{pairs:[{before, after, status, note}]}`, `before`/`after` — названия из переданных списков или `""` (проверяй, иначе пара отбрасывается), `status` ∈ kept|transformed|created|abolished. `sources` у `UnitChange` — объединение источников обоих Unit; `note` — коротко по-русски.
4. Mock-режим: `LLM.complete_json` читает только `mocks/<name>.json`, поэтому в `units.py` при `llm.mode == "mock"` сам читай `mocks/extract_units/<hash>.json` и `mocks/match_units/<hash>.json`, где `hash = sha256(json.dumps(user_payload, ensure_ascii=False, sort_keys=True))[:16]`; нет файла — `LLMError` с именем ожидаемого файла, не подмена. Положи фикстуры для тестового комплекта (`data/case11/*.txt` — те же docx текстом): редакция 8 — ДНМ, ДККМ, направление внутреннего аудита, БВА (п. 3.4–3.8); редакция 9 — ДИТААД, ДОА, ДНМ, ДККМ (п. 3.4–3.9). Ожидаемый результат: ДНМ, ДККМ, БВА — kept; ДИТААД, ДОА — created; направление внутреннего аудита — transformed или abolished с note. Формат фикстур — как живой ответ модели, чтобы S11 заменил их реальными без правки кода.
5. `tests/test_units.py`: `Document` для теста строй сам из `data/case11/*.txt` (строка вида `3.4. …` → `Clause`, буква `а.` — подпункт предыдущего) — парсер S04 не жди. Проверь: детерминированное сопоставление без LLM; отбрасывание чужого `clause_number`; каждый `UnitChange` имеет непустые `sources`; на комплекте — created ≥ 2, kept ≥ 2; отсутствие фикстуры даёт `LLMError`.

**Done-when:** `cd backend && LLM_MODE=mock uv run pytest -q tests/test_units.py`.
**Cut-if:** `match_units` только детерминированный (`transformed` не находим, честно пишем `abolished`/`created`), LLM-шаг остаётся в коде за флагом.

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/units`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S05): <что сделано>" && git push -u origin s/units`.
Затем создай `status/agents/S05.md` в этом worktree: первая строка `# S05 — ЗЕЛЕНО` или `# S05 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
