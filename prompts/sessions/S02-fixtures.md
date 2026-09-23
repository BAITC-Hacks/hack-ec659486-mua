# S02 — Фикстуры отчёта (волна 1, 14:20–14:40, B, ветка `s/fixtures`)

Прочитай `AGENTS.md`, `docs/case.md`, `docs/spec-case11.md` §1, §3; типы возьми из `frontend/lib/types.ts` и `backend/app/schemas.py` в ветке `s/contract`, если они уже запушены (`git fetch origin s/contract && git show origin/s/contract:backend/app/schemas.py`), иначе — из spec §3.

**Пишешь только в:** `frontend/lib/fixtures/report.ts`, `frontend/lib/fixtures/run.ts`, `backend/app/mocks/demo_report.json`, `backend/tests/test_fixtures_valid.py`.
**Не трогаешь:** схемы, типы, страницы.

Задача: дать фронту правдоподобный Report раньше, чем появится пайплайн, и закрепить его тестом.

Сделай:
1. `Report` для тестового комплекта из `data/case11/*.txt` (это те же docx текстом): реальные названия из документов — «Блок внутреннего аудита», «Главный аудитор», подразделения из раздела 3, ДЗО; 3 UnitChange (сохранено, преобразовано, создано), 8 FunctionMatch (по два kept/changed/lost/new/moved; `before`/`after` — списки, один из них `kind: "split"`, один `lost` с `verified: false` и `note` «требует проверки»; у каждого `verified`, `verification`), 2 Duplicate (`verified`, `verification_note`), 1 Conflict (правило «выполняет и контролирует», `role_pattern`, `verified`), 1–2 функции в `constraints` (`modality: "prohibition"` под «не имеют права:»), `conclusion_md` на 10 строк, `stats` с `unverified_candidates`. Все `sources` — с настоящими номерами пунктов и цитатами из `data/case11/*.txt` (скопируй дословно, 1–2 предложения).
2. Тот же объект в `backend/app/mocks/demo_report.json`.
3. `frontend/lib/fixtures/run.ts` — RunStatus для трёх состояний: parsing 5%, verification 65%, done 100% (статусы только из spec §4).
4. `backend/tests/test_fixtures_valid.py`: `demo_report.json` валидируется моделью `Report` из `schemas.py` (если схем ещё нет — тест проверяет наличие обязательных ключей верхнего уровня и что у каждой находки непустой `sources`).

**Done-when:** `cd backend && uv run pytest -q tests/test_fixtures_valid.py` зелёный.
**Cut-if:** одна Duplicate и один UnitChange каждого типа.

В конце выведи список изменённых файлов и вывод Done-when.


## Дополнение по аудиту

- Не задавай произвольные числа находок: возьми примеры из `data/case11/diff-8-vs-9.md` (реорганизация 3.4 а/б → ДИТААД/ДОА, потеря-кандидат 3.6 ред. 8, новый пункт «информирует о потенциальном конфликте…»). Значения enum и `null` — как в `schemas.py`.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/fixtures`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S02): <что сделано>" && git push -u origin s/fixtures`.
Затем создай `status/agents/S02.md` в этом worktree: первая строка `# S02 — ЗЕЛЕНО` или `# S02 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
