# S11 — Дубли и конфликты интересов (волна 3, 15:20–16:00, A, ветка `s/conflicts`)

Прочитай `AGENTS.md`, `docs/case.md` (условие 3 — твоё), `docs/spec-case11.md` §2 P5, §3, §5; `backend/app/llm.py` (`LLM.complete_json`, `strict_schema`, `LLMError`, `llm.mode`); модели `Function`, `Duplicate`, `Conflict`, `Source` из `backend/app/schemas.py`; `backend/app/prebuilt/lib_normalize.py` (`signature`, `verb_class`, `object_head`); образец фикстур по хэшу — `git show origin/s/units:backend/app/units.py`.

**Пишешь только в:** `backend/app/duplicates.py`, `backend/app/rules/__init__.py`, `backend/app/rules/conflicts.py`, `backend/app/prompts/find_duplicates.md`, `backend/app/prompts/explain_conflict.md`, `backend/app/mocks/find_duplicates/**`, `backend/app/mocks/explain_conflict/**`, `backend/tests/test_conflicts.py`.
**Не трогаешь:** `main.py`, `schemas.py`, `llm.py`, `prebuilt/`, `pipeline.py`, чужие модули и тесты, фронт. Новых зависимостей нет.

Задача: `find_duplicates(functions_by_unit: dict[str, list[Function]], llm: LLM) -> list[Duplicate]` и `find_conflicts(functions_by_unit, llm) -> list[Conflict]` для одной версии документа. Каждая находка — с `sources` обеих функций; без источника не возвращать.

Сделай:
1. `duplicates.py`, код: одинаковая `signature` у функций **разных** подразделений → `Duplicate(similarity=1.0, note="одинаковая сигнатура")`; внутри одного подразделения не сравнивать. Затем LLM `find_duplicates` только для пар подразделений с общим `verb_class` и разными сигнатурами: system — `prompts/find_duplicates.md` (по-русски: эквивалентность по смыслу; id не выдумывать), user — JSON `{unit_a, unit_b, functions_a:[{id, text}], functions_b:[{id, text}]}` (≤ 40 функций), schema — `strict_schema` модели `{pairs:[{a_id, b_id, similarity, note}]}`. Чужой id или `similarity < 0.7` → пара отбрасывается с `logger.warning`.
2. `rules/conflicts.py`: правила а–г из spec §2 P5 как детерминированные проверки над `verb_class`/`object_head`: (а) одно подразделение по одному объекту имеет исполняющий класс (СОЗДАВАТЬ/ОРГАНИЗОВЫВАТЬ/ВЕСТИ_УЧЁТ/ЭКСПЛУАТИРОВАТЬ) и КОНТРОЛИРОВАТЬ; (б) инициирует («иницииру», «вносит», «предлага») и СОГЛАСОВЫВАТЬ по одному объекту; (в) подразделение с «аудит» в названии имеет операционные функции (не КОНТРОЛИРОВАТЬ/ОТЧИТЫВАТЬСЯ/ОБУЧАТЬ/МЕТОДОЛОГИЯ); (г) объект контрольной функции — само подразделение или его руководитель. `RULES = [(rule_id, title, check)]`.
3. LLM `explain_conflict` только для найденных пар: user — JSON `{rule_id, title, units, functions:[{id, unit, text, clause_number}]}`, schema `{explanation, severity}` (`severity` — Literal low|medium|high). `Conflict.sources` — из всех функций пары; номера пунктов в `explanation` не из переданных — удалять; пустой ответ → `explanation="объяснение не получено"` и `logger.warning`.
4. Mock-режим: при `llm.mode == "mock"` читай `mocks/<name>/<hash>.json`, `hash = sha256(json.dumps(user_payload, ensure_ascii=False, sort_keys=True))[:16]`; нет файла — `LLMError` с именем ожидаемого файла. Пустые кандидаты — LLM не вызывать. Фикстуры для тестовых случаев — в формате живого ответа.
5. `tests/test_conflicts.py` (`LLM_MODE=mock`, `Function` собирай руками, пункты «2.4.», «5.1.» и цитаты — дословно из `data/case11/*.txt`): одна сигнатура у двух подразделений → один `Duplicate`; внутри одного — ничего; правило (а) на «проводит проверку X» + «организует X» → `Conflict` с `rule_id="a"`, непустыми `sources` и `severity`; правило (в) на «Блок внутреннего аудита» с операционной функцией; чужой id в фикстуре отброшен; нет фикстуры → `LLMError`; пустой вход → пустые списки без вызова LLM (счётчик через monkeypatch).

**Done-when:** `cd backend && LLM_MODE=mock uv run pytest -q tests/test_conflicts.py`
**Cut-if:** LLM `find_duplicates` не вызывается — дубли только по сигнатуре; правила только (а) и (в); `explanation` собирается кодом из `title` и цитат с `note` «объяснение LLM не выполнено».

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/conflicts`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S11): <что сделано>" && git push -u origin s/conflicts`.
Затем создай `status/agents/S11.md` в этом worktree: первая строка `# S11 — ЗЕЛЕНО` или `# S11 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
