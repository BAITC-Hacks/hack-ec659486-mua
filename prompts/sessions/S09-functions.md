# S09 — Извлечение функций по пунктам (волна 3, 15:20–16:00, A, ветка `s/functions`)

Прочитай `AGENTS.md`, `docs/case.md` (условия 2–4 опираются на твой шаг), `docs/spec-case11.md` §2 P3, §3, §5; `backend/app/llm.py` (`LLM`, `complete_json`, `strict_schema`, `LLMError`, `llm.mode`); `backend/app/prebuilt/lib_normalize.py` (`signature`); модели `Document`, `Clause`, `Source`, `Unit`, `Function` из `backend/app/schemas.py`; `backend/app/units.py` из `origin/s/units` (фикстуры по хэшу — как там).

**Пишешь только в:** `backend/app/functions.py`, `backend/app/prompts/extract_functions.md`, `backend/app/mocks/extract_functions/**`, `backend/tests/test_functions.py`.
**Не трогаешь:** `main.py`, `schemas.py`, `llm.py`, `units.py`, `prebuilt/`, `routers/`, `pipeline.py`, фронт.

Задача: `extract_functions(doc: Document, unit: Unit | None, llm: LLM) -> list[Function]` — атомарные функции с категорией, сигнатурой и пунктом-источником; `extract_all(doc, units, llm) -> list[Function]` для документа целиком. Результат сопоставляет S10.

Сделай:
1. Выбор пунктов: для `unit` — пункты, где встречается название или аббревиатура подразделения (нормализация как в S05), плюс пункты из `unit.sources`. Если `units` пуст или пунктов никому не досталось — функции всего документа: разделы 2 («Цели, задачи и функции») и 5 («Права и обязанности»), `unit_id` = id корневого подразделения (БВА) или `""`. Пункты без номера и заголовки разделов не передавать.
2. `prompts/extract_functions.md` (system, по-русски): один пункт → одна или несколько атомарных функций; текст — короткая формулировка из пункта без пересказа; `category` ∈ задача|функция|право|обязанность|ответственность (раздел 2.3 — задачи, 2.4 — функции, 5.x — права/обязанности по глаголу); `clause_number` только из переданного списка; ничего не додумывать. User — JSON `{version, unit, clauses:[{number, text}]}`.
3. Схема: pydantic `{functions:[{text, category, clause_number}]}`, `category` — Literal, через `strict_schema`. Ответ проверяй кодом: `clause_number` не из переданного множества или пустой `text` — функция отбрасывается с `logger.warning`; ошибка схемы — `LLMError`, не пустой список молча.
4. `Function`: `id = sha1(doc.id + clause_number + text)[:12]`, `signature = lib_normalize.signature(text)`, `sources = [Source(doc_id, doc_name, version, clause_number, quote=текст пункта дословно)]`.
5. Кэш и mock: `hash = sha256(json.dumps(user_payload, ensure_ascii=False, sort_keys=True))[:16]`. Live — результат в памяти по хэшу (повторный вызов без LLM). Mock — читай `mocks/extract_functions/<hash>.json`; нет файла — `LLMError` с именем ожидаемого файла. Для стабильного хэша пункты в payload сортируй по `index`.
6. Фикстуры для тестового комплекта (`data/case11/*.txt` — те же docx текстом): редакции 8 и 9, функции из разделов 2 и 5, формат — как живой ответ модели (S11 заменит реальными без правки кода). Минимум по 15 функций на редакцию, обязательно 2.4.2, 2.4.9, 2.4.10, 5.1.1, 5.1.4.
7. `tests/test_functions.py` (Document строй из txt сам, как S05): на комплекте ≥ 15 функций у каждой редакции, у каждой непустые `sources` и `signature`, номер пункта есть в документе, `quote` равен тексту пункта; чужой `clause_number` в фикстуре → функция отброшена; нет фикстуры → `LLMError`; повторный вызов не обращается к `LLM` (счётчик через monkeypatch).

**Done-when:** `cd backend && LLM_MODE=mock uv run pytest -q tests/test_functions.py`
**Cut-if:** категория только задача|функция|обязанность; привязка к подразделению не делается — все функции документа с `unit_id=""`, честно отмечено в `note` статуса.

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/functions`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S09): <что сделано>" && git push -u origin s/functions`.
Затем создай `status/agents/S09.md` в этом worktree: первая строка `# S09 — ЗЕЛЕНО` или `# S09 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
