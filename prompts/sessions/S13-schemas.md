# S13 — Схемы LLM-вызовов (волна 3, 15:20–16:00, B, ветка `s/schemas`)

Прочитай `AGENTS.md`, `docs/case.md`, `docs/spec-case11.md` §2, §3 и §5 целиком; `backend/app/llm.py` (там уже есть `strict_schema(model)`, `_make_strict`, `validate_output`, `LLMError` — используй их, не дублируй).

**Пишешь только в:** `backend/app/llm_schemas.py`, `backend/tests/test_llm_schemas.py`.
**Не трогаешь:** `llm.py`, `schemas.py`, `main.py`, промпты, модули пайплайна, чужие тесты.

Задача: единая точка правды для восьми выходов LLM из spec §5, чтобы S09/S10/S11/S14 брали схему по имени и не писали свои, и общий фильтр выдуманных номеров пунктов. Принцип spec §2: похожесть (сигнатура, BM25, косинус) — только кандидат; статус ставят только проверочные вызовы `verify_matches`, `confirm_loss`, `verify_duplicates`, `explain_conflict` по строгой схеме.

Сделай:
1. Pydantic-модели ответов ровно по spec §5, `model_config = ConfigDict(extra="forbid")`, все поля обязательные, статусы — `Literal`:
   - `ExtractUnitsOut {units:[{name, parent: str, clause_numbers:[str]}]}` — `parent` пустая строка `""`, если нет (так уже пишет S05, фикстуры должны совпадать);
   - `MatchUnitsOut {pairs:[{before: str, after: str, status: kept|transformed|created|abolished, note}]}` — `before`/`after` — название из переданного списка или `""` (как в S05);
   - `ExtractFunctionsOut {functions:[{text, category: task|function|right|duty|responsibility, executor: str|None, modality: duty|right|prohibition|neutral, clause_number, context_clause_numbers:[str]}]}` — `executor` (подразделение или должность из заголовка/lead_in/текста), `modality` по spec P1; `prohibition` — ограничение, не функция;
   - `VerifyMatchesOut {decision: kept|changed|moved|split|merge|partial|none, after_ids:[str], rationale, quotes:[str]}` — одна функция «до» против ≤ 5 кандидатов «после»; при `none` `after_ids` пустой;
   - `ConfirmLossOut {lost: bool, nearest_clause_number: str|None, nearest_quote, rationale}` — подтверждение потери после поиска по всему документу «после»;
   - `VerifyDuplicatesOut {is_duplicate: bool, same_action: bool, same_object: bool, both_executors: bool, verification_note}` — дубль только если все три признака истинны (одно действие над одним объектом у двух разных исполнителей, ни одна сторона не «участвует/содействует/соисполнитель» и не просто ссылается на документ); добавь `model_validator`, который запрещает `is_duplicate=True` при любом ложном признаке;
   - `ExplainConflictOut {explanation, severity: low|medium|high, verified: bool, verification_note}`;
   - `WriteConclusionOut {conclusion_md, recommendations:[str]}`.
2. Константы `EXTRACT_UNITS_SCHEMA … WRITE_CONCLUSION_SCHEMA = strict_schema(<модель>)` и словарь `SCHEMAS: dict[str, tuple[type[BaseModel], dict]]` с ключами-именами вызовов из spec §5: `extract_units`, `match_units`, `extract_functions`, `verify_matches`, `confirm_loss`, `verify_duplicates`, `explain_conflict`, `write_conclusion` — ровно восемь. Никаких `match_functions` и `find_duplicates`: похожесть статус не ставит.
3. `validate_clause_numbers(result: dict, allowed: set[str]) -> dict`: возвращает копию, где из `units[*].clause_numbers` выброшены номера не из `allowed` (юнит без остатка — удалён); из `functions` удалены записи с чужим `clause_number`, а из `context_clause_numbers` — чужие номера; в `verify_matches` из `after_ids` выброшены идентификаторы не из `allowed` (пустой остаток при `decision != none` — `decision` не чинится, запись помечать не нужно: вызывающий модуль сам переведёт в «кандидат, не проверено»); в `confirm_loss` `nearest_clause_number` не из `allowed` → `None`; для остальных схем — без изменений. Ничего не выдумывает и не «чинит» номера, только отбрасывает; количество отброшенных пиши в `logger.info`.
4. Тесты в `test_llm_schemas.py` (без ключа, без сети, без `jsonschema` — её нет в зависимостях): для каждой из восьми схем — (а) структура: корень `type: object`, в каждом объекте по дереву, включая `$defs`, `additionalProperties is False` и `required == list(properties)`; (б) пример ответа из spec §5 проходит `model_validate`; (в) тот же пример с лишним полем — `ValidationError`; (г) `validate_clause_numbers` на примере с одним чужим номером удаляет ровно его и не трогает остальное (для `extract_units`, `extract_functions`, `verify_matches`, `confirm_loss`); (д) `VerifyDuplicatesOut` с `is_duplicate=True` и `same_object=False` — `ValidationError`; `VerifyMatchesOut` принимает все семь `decision`. Примеры — с реальными номерами пунктов из `data/case11/*.txt` (вид «3.2.», раздел 3).

Не пиши промпты, вызовы `complete_json` и фикстуры — это S09/S10/S11/S14.

**Done-when:** `cd backend && uv run pytest -q tests/test_llm_schemas.py` зелёный.
**Cut-if:** тест (г) только для `extract_functions` и `verify_matches`; `validate_clause_numbers` — только для `extract_units`, `extract_functions`, `verify_matches`; тест (д) и `model_validator` дублей — убрать.

В конце выведи список изменённых файлов и вывод Done-when.


## Дополнение по аудиту: согласование с контрактом

- Значения enum и семантика пустых значений (`null`) — строго как в `backend/app/schemas.py`; никаких параллельных перечислений. Схемы вызовов принимают/возвращают `clause_id` и `clause_number` вместе.
- Добавь проверку `validate_sources(result, documents)`: адрес существует, цитата является подстрокой текста пункта (после нормализации пробелов), и для функций — исполнитель находки совпадает с исполнителем пункта или его `lead_in`. Находка, не прошедшая проверку, помечается `verified=false` с причиной, не удаляется молча.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/schemas`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S13): <что сделано>" && git push -u origin s/schemas`.
Затем создай `status/agents/S13.md` в этом worktree: первая строка `# S13 — ЗЕЛЕНО` или `# S13 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
