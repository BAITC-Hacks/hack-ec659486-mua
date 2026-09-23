# S10 — Сопоставление функций до↔после (волна 3, 15:20–16:00, A, ветка `s/matching`)

Прочитай `AGENTS.md`, `docs/case.md` (условие 2 — потеря функций — твоё), `docs/spec-case11.md` §2 P4, §3, §5; `backend/app/llm.py` (`LLM.complete_json`, `strict_schema`, `LLMError`, mock-режим); модели `Function`, `FunctionMatch`, `Source` из `backend/app/schemas.py`; `backend/app/prebuilt/lib_normalize.py` (`signature`); как образец работы с фикстурами по хэшу — `backend/app/units.py` из S05 (`git fetch origin s/units && git show origin/s/units:backend/app/units.py`).

**Пишешь только в:** `backend/app/matching.py`, `backend/app/prompts/match_functions.md`, `backend/app/mocks/match_functions/**`, `backend/tests/test_matching.py`.
**Не трогаешь:** `main.py`, `schemas.py`, `llm.py`, `prebuilt/`, `pipeline.py`, чужие модули и тесты, фронт. Новых зависимостей нет.

Задача: `match_functions(before: list[Function], after: list[Function]) -> list[FunctionMatch]` — каждая функция «до» и «после» попадает ровно в одну пару со статусом kept / changed / lost / new / moved, `confidence` и `note`; у каждой пары оба `Source` (через `before.sources` и `after.sources`, у односторонних пар — только имеющаяся сторона).

Сделай:
1. Шаг 1, код: нормализованный текст (нижний регистр, ё→е, без пунктуации и лишних пробелов) совпал → `kept`, `confidence` 1.0. Шаг 2, код: одинаковая `signature` (поле `Function.signature`) → `changed`, если `unit_id` тот же, иначе `moved`; `confidence` 0.8; в `note` — что именно изменилось (текст/подразделение). Сопоставление один-к-одному: использованные функции из кандидатов убираются.
2. Шаг 3, LLM `match_functions` для остатка: system — текст `prompts/match_functions.md` (по-русски: сопоставить по смыслу, определения статусов, id не выдумывать), user — JSON `{before:[{id, unit, text}], after:[{id, unit, text}]}` пакетами ≤ 60 функций суммарно, по порядку, schema — `strict_schema` модели `{matches:[{before_id, after_id, status, note}]}`, `before_id`/`after_id` — id из переданных списков или `""`. Проверяй кодом: чужой id или уже использованный → пара отбрасывается с `logger.warning`; `status` ∉ kept|changed|lost|new|moved → отбрасывается. `confidence` LLM-пар 0.6. Всё, что осталось без пары после LLM: «до» → `lost`, «после» → `new`, `confidence` 0.5, `note` «пара не найдена».
3. Mock-режим: при `llm.mode == "mock"` читай `mocks/match_functions/<hash>.json`, `hash = sha256(json.dumps(user_payload, ensure_ascii=False, sort_keys=True))[:16]`; нет файла — `LLMError` с именем ожидаемого файла, не пустой ответ. Пустой остаток — LLM не вызывать. Фикстура для случая из теста — в формате живого ответа, чтобы S11 заменил её реальной без правки кода.
4. `tests/test_matching.py` (без ключа, `LLM_MODE=mock`): `Function` собирай руками с `Source` (пункты вида «2.3.», цитаты — из `data/case11/*.txt`). Случай: пять функций «до», из них одна удалена → `lost`; одна переформулирована с той же `signature` → `changed`; одна с тем же текстом в другом `unit_id` → `moved`; неизменные → `kept`; одна новая «после» → `new`. Проверь: сумма пар покрывает все функции ровно один раз; у каждой пары непустые `sources` на имеющейся стороне; чужой id из фикстуры отбрасывается; нет фикстуры → `LLMError`; пустые списки → пустой результат без вызова LLM.

**Done-when:** `cd backend && LLM_MODE=mock uv run pytest -q tests/test_matching.py`
**Cut-if:** LLM-шаг остаётся в коде, но остаток размечается кодом как `lost`/`new` с `note` «сопоставление по смыслу не выполнено»; `moved` — только по сигнатуре.

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/matching`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S10): <что сделано>" && git push -u origin s/matching`.
Затем создай `status/agents/S10.md` в этом worktree: первая строка `# S10 — ЗЕЛЕНО` или `# S10 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
