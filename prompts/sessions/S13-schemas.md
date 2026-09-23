# S13 — Схемы LLM-вызовов (волна 3, 15:20–16:00, B, ветка `s/schemas`)

Прочитай `AGENTS.md`, `docs/case.md`, `docs/spec-case11.md` §2 и §5 целиком; `backend/app/llm.py` (там уже есть `strict_schema(model)`, `_make_strict`, `validate_output`, `LLMError` — используй их, не дублируй).

**Пишешь только в:** `backend/app/llm_schemas.py`, `backend/tests/test_llm_schemas.py`.
**Не трогаешь:** `llm.py`, `schemas.py`, `main.py`, промпты, модули пайплайна, чужие тесты.

Задача: единая точка правды для семи выходов LLM из spec §5, чтобы S09/S10/S14 брали схему по имени и не писали свои, и общий фильтр выдуманных номеров пунктов.

Сделай:
1. Pydantic-модели ответов ровно по spec §5, `model_config = ConfigDict(extra="forbid")`, все поля обязательные, статусы — `Literal`: `ExtractUnitsOut {units:[{name, parent: str|None, clause_numbers:[str]}]}`, `MatchUnitsOut {pairs:[{before: str|None, after: str|None, status: kept|transformed|created|abolished, note}]}`, `ExtractFunctionsOut {functions:[{text, category: task|function|right|duty|responsibility, clause_number}]}`, `MatchFunctionsOut {matches:[{before_id: str|None, after_id: str|None, status: kept|changed|lost|new|moved, note}]}`, `FindDuplicatesOut {pairs:[{a_id, b_id, similarity: 0..1, note}]}`, `ExplainConflictOut {explanation, severity: low|medium|high}`, `WriteConclusionOut {conclusion_md, recommendations:[str]}`.
2. Константы `EXTRACT_UNITS_SCHEMA … WRITE_CONCLUSION_SCHEMA = strict_schema(<модель>)` и словарь `SCHEMAS: dict[str, tuple[type[BaseModel], dict]]` с ключами-именами вызовов из spec §5 (`extract_units`, `match_units`, …) — ровно семь.
3. `validate_clause_numbers(result: dict, allowed: set[str]) -> dict`: возвращает копию, где из `units[*].clause_numbers` выброшены номера не из `allowed` (юнит без остатка — удалён), из `functions` удалены записи с чужим `clause_number`; для остальных схем — без изменений. Ничего не выдумывает и не «чинит» номера, только отбрасывает; количество отброшенных пиши в `logger.info`.
4. Тесты в `test_llm_schemas.py` (без ключа, без сети, без `jsonschema` — её нет в зависимостях): для каждой из семи схем — (а) структура: корень `type: object`, в каждом объекте по дереву, включая `$defs`, `additionalProperties is False` и `required == list(properties)`; (б) пример ответа из spec §5 проходит `model_validate`; (в) тот же пример с лишним полем — `ValidationError`; (г) `validate_clause_numbers` на примере с одним чужим номером удаляет ровно его и не трогает остальное. Примеры — с реальными номерами пунктов из `data/case11/*.txt` (вид «3.2.», раздел 3).

Не пиши промпты, вызовы `complete_json` и фикстуры — это S09/S10/S11.

**Done-when:** `cd backend && uv run pytest -q tests/test_llm_schemas.py` зелёный.
**Cut-if:** тест (г) только для `extract_functions`; `validate_clause_numbers` — только для `extract_units` и `extract_functions`.

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/schemas`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S13): <что сделано>" && git push -u origin s/schemas`.
Затем создай `status/agents/S13.md` в этом worktree: первая строка `# S13 — ЗЕЛЕНО` или `# S13 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
