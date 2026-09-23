# Сессии 23.09, кейс 11 «ОргДифф»: 20 пишущих сессий волнами, старт 14:15

Кодинг до 18:00, **freeze 17:15**, сдача 17:45. Промпты — `prompts/sessions/SNN-*.md`, лист запуска по волнам —
`prompts/sessions/README.md`, пошаговый runbook — `docs/runbook-gui.md`, схема «три собеседника + автономные окна» — `docs/mix.md`.

Один репозиторий (5.4.11), ветки: `main` — только через мерж-поезд; `s/*` — по одной на пишущую сессию;
`ops/audit` — orphan для отчётов аудита, в `main` не мержится никогда.

## Три правила, без которых параллельность не работает

**1. Розетки делаются в первой волне, потом закрыты.** Главный источник конфликтов — файлы, которые трогают все:
`backend/app/main.py` (регистрация роутеров), `backend/app/schemas.py` и `frontend/lib/types.ts` (контракт),
`frontend/app/layout.tsx` (навигация). Поэтому S01 создаёт схемы, типы, роутер `runs` с заглушками и регистрирует его
в `main.py`; S03 делает навигацию и **все пустые страницы** (`/`, `/runs/[id]`, `/report/[id]`) и общие компоненты
(`status-badge`, `ui/tabs`). **После S01 и S03 эти файлы не трогает никто до конца дня**: `main.py`, `schemas.py`,
`types.ts`, `layout.tsx` закрыты. Дальше каждая сессия пишет только в свои файлы, и конфликтовать физически нечем.
Если модулю не хватает поля в схеме — он добавляет минимально у себя и пишет об этом в отчёт, интегратор решает.

**2. Сессия закрывается командой, а не чтением кода.** У каждой сессии есть Done-when — команда, которая или зелёная,
или нет (`uv run pytest -q tests/test_X.py`, `npm run build`). Ревью = запустить команду, 30 секунд. Автономные сессии
сами гоняют Done-when до зелёного, коммитят, пушат ветку и пишут `status/agents/SNN.md` (первая строка ЗЕЛЕНО/КРАСНО).
Если сессия не может предъявить команду (S15 живой прогон, S18–S20 доки), она интерактивная и ведётся человеком.

**3. Мержит один человек — B — в фиксированном порядке.** `scripts/ops/merge-train.sh "<ветки>"` из чистого `main`:
бэкенд-данные → бэкенд-модель → бэкенд-роутеры → фронт-компоненты → фронт-страницы → тесты → доки.
После каждого мержа — проверка (`CHECK`, по умолчанию `make check`). Красное — ветка откатывается из поезда
и чинится в своём worktree, **`main` не чинится**. Перед поездом `git pull --rebase origin main`.

## Матрица владения файлами, волны 1–5

Собрана из строк «Пишешь только в» всех промптов. В каждой волне у файла один владелец; между волнами файл переходит.
**Жирным** — единственный владелец в волне; «(пусто)» — заглушка; «(+)» — только добавление, не переписывание.

| Файл / каталог | В1 14:15–14:40 | В2 14:40–15:20 | В3 15:20–16:00 | В4 16:00–16:40 | В5 16:40–17:15 |
|---|---|---|---|---|---|
| `backend/app/main.py` | **S01** | — | — | — | — |
| `backend/app/schemas.py` | **S01** | — | — | — | — |
| `frontend/lib/types.ts` | **S01** | — | — | — | — |
| `backend/app/routers/runs.py` | S01 (пусто) | **S08** | — | S16 (+ вызовы `validate_*`, `with_timeout`, один `except`) | — |
| `backend/app/store.py` | S01 (dict + get/put) | **S08** | — | — | — |
| `backend/app/pipeline.py` | — | **S08** | — | — | — |
| `backend/tests/test_contract_smoke.py` | **S01** | — | — | — | — |
| `backend/tests/test_runs.py` | — | **S08** | — | — | — |
| `backend/app/parse/__init__.py`, `parse/docx.py` | — | **S04** | — | — | — |
| `backend/tests/test_parse.py` | — | **S04** | — | — | — |
| `backend/app/units.py` | — | **S05** | — | — | — |
| `backend/app/prompts/extract_units.md`, `match_units.md` | — | **S05** | — | — | — |
| `backend/app/mocks/extract_units/**`, `mocks/match_units/**` | — | **S05** | — | S15 (замена на реальные) | — |
| `backend/tests/test_units.py` | — | **S05** | — | — | — |
| `backend/app/mocks/demo_report.json` | **S02** | — | — | S15 (при необходимости) | — |
| `backend/tests/test_fixtures_valid.py` | **S02** | — | — | — | — |
| `frontend/lib/fixtures/report.ts`, `fixtures/run.ts` | **S02** | — | — | — | — |
| `frontend/app/layout.tsx` | **S03** | — | — | — | — |
| `frontend/components/status-badge.tsx`, `ui/tabs.tsx` | **S03** | — | — | — | — |
| `frontend/app/page.tsx` | S03 (пусто) | **S06** | — | — | — |
| `frontend/components/upload-box.tsx` | — | **S06** | — | — | — |
| `frontend/lib/api-runs.ts` | — | **S06** | S12 (+ `getClause`, `useFixtures`) | — | — |
| `frontend/app/report/[id]/page.tsx` | S03 (пусто) | **S07** | S12 (только источник данных + импорт `SourceDrawer`) | — | — |
| `frontend/components/units-table.tsx`, `function-matrix.tsx`, `duplicates-list.tsx`, `conflicts-list.tsx`, `conclusion-view.tsx` | — | **S07** | — | — | — |
| `frontend/app/runs/[id]/page.tsx` | S03 (пусто) | — | **S12** | — | — |
| `frontend/components/run-progress.tsx`, `source-drawer.tsx` | — | — | **S12** | — | — |
| `backend/app/functions.py` | — | — | **S09** | — | — |
| `backend/app/prompts/extract_functions.md` | — | — | **S09** | — | — |
| `backend/app/mocks/extract_functions/**` | — | — | **S09** | S15 (замена) | — |
| `backend/tests/test_functions.py` | — | — | **S09** | — | — |
| `backend/app/matching.py` | — | — | **S10** | — | — |
| `backend/app/prompts/match_functions.md` | — | — | **S10** | — | — |
| `backend/app/mocks/match_functions/**` | — | — | **S10** | S15 (замена) | — |
| `backend/tests/test_matching.py` | — | — | **S10** | — | — |
| `backend/app/duplicates.py` | — | — | **S11** | — | — |
| `backend/app/rules/__init__.py`, `rules/conflicts.py` | — | — | **S11** | — | — |
| `backend/app/prompts/find_duplicates.md`, `explain_conflict.md` | — | — | **S11** | — | — |
| `backend/app/mocks/find_duplicates/**`, `mocks/explain_conflict/**` | — | — | **S11** | S15 (замена) | — |
| `backend/tests/test_conflicts.py` | — | — | **S11** | — | — |
| `backend/app/llm_schemas.py` | — | — | **S13** | — | — |
| `backend/tests/test_llm_schemas.py` | — | — | **S13** | — | — |
| `backend/app/conclusion.py`, `export_md.py` | — | — | — | **S14** | — |
| `backend/app/prompts/write_conclusion.md` | — | — | — | **S14** | — |
| `backend/app/mocks/write_conclusion/**` | — | — | — | **S14**, затем S15 (только после ЗЕЛЕНО S14, см. ниже) | — |
| `backend/tests/test_conclusion.py` | — | — | — | **S14** | — |
| `backend/app/validation.py` | — | — | — | **S16** | — |
| `backend/tests/test_validation.py` | — | — | — | **S16** | — |
| `backend/tests/test_e2e_mock.py` | — | — | — | **S17** | — |
| `deploy/smoke.sh` | — | — | — | **S17** | — |
| `README.md` | — | — | — | — | **S18** |
| `docs/ai-usage.md` | — | — | — | — | **S19** |
| `docs/img/**` | — | — | — | — | **S20** |
| `status/agents/SNN.md` | каждая сессия — только свой файл | | | | |

Никто, ни в какой волне: `backend/app/llm.py`, `backend/app/config.py`, `backend/app/prebuilt/**` (заготовки, раскрыты в README §12),
`frontend/lib/api.ts`, `frontend/components/ui/*` (кроме `tabs.tsx` в S03), `docker-compose.yml`, `pyproject.toml`, `package.json`
(новых зависимостей нет ни у кого).

### Проверка пересечений (23.09 14:10)

Внутри каждой волны две сессии не пишут в один файл — проверено по строкам «Пишешь только в» S01–S17 и S18–S20.

Найдено и исправлено:
- **S01**: `backend/app/store.py` создавался по п. 3 задания, но не был указан в «Пишешь только в» — добавлен туда
  (с пометкой «только dict + get/put»), и уточнено, что `routers/runs.py` и `store.py` в волне 2 перепишет S08,
  а `main.py`, `schemas.py`, `types.ts` закрыты до конца дня (раньше стояло «до волны 4», хотя в волне 4 их тоже никто не правит).
  Пересечения с S02/S03 нет, это была неполнота строки.

Не пересечения, но зависимость по порядку (отмечены в матрице):
- **В4, `backend/app/mocks/write_conclusion/**`**: S14 (автономно) и S15 (A руками с ключом) в одной волне. S15 — ручная
  сессия A, стартует после отчёта ЗЕЛЕНО от S14 и пишет в `mocks/write_conclusion/` только после мержа `s/conclusion`
  (или не трогает его: у S14 фикстура уже реальная, если ключ был в `.env`). Остальные каталоги `mocks/*` S15 заменяет
  свободно — их владельцы (S05, S09–S11) уже влиты волнами 2–3.
- **В4, `backend/app/routers/runs.py`**: только S16, и только добавлением вызовов. S14 роутер не трогает, подключение
  `conclusion`/`export_md` в пайплайн — через ленивый `getattr` в `pipeline.py` (S08), правки не нужны.
- **В3, `frontend/app/report/[id]/page.tsx`** и `lib/api-runs.ts`: единственный владелец S12; S06/S07 (владельцы волны 2)
  к этому моменту влиты.

## Волны, коротко (полный лист — `prompts/sessions/README.md`)

| Волна | Время | A | B | Мерж-поезд (B) |
|---|---|---|---|---|
| 1 | 14:15–14:40 | S01 `s/contract` (интерактивно) | S03 `s/ui-shell` (интерактивно), S02 `s/fixtures` (автономно, с 14:20) | `s/contract s/fixtures s/ui-shell` |
| 2 | 14:40–15:20 | S04 `s/parse`, S05 `s/units`, S08 `s/runs` | S06 `s/ui-upload`, S07 `s/ui-report` | `s/parse s/units s/runs s/ui-upload s/ui-report` |
| 3 | 15:20–16:00 | S09 `s/functions`, S10 `s/matching`, S11 `s/conflicts` | S12 `s/ui-wire`, S13 `s/schemas` | `s/schemas s/functions s/matching s/conflicts s/ui-wire` |
| 4 | 16:00–16:40 | S14 `s/conclusion`; S15 `s/live-fixtures` руками с ключом | S16 `s/validation`, S17 `s/e2e` | `s/conclusion s/live-fixtures s/validation s/e2e` |
| 5 | 16:40–17:15 | S19 `s/disclosure` | S18 `s/readme`, S20 `s/img`; чистый прогон по README | `s/disclosure s/img s/readme` |
| freeze | 17:15–17:45 | чистый прогон на теге `green-17` | видео, форма сдачи 17:45 | финальный push |

**16:00 — контрольная точка:** «Тестовый комплект» → прогресс → отчёт с четырьмя вкладками на живом API в mock-режиме.
Если нет — волна 4 режется: S14 в Cut-if, S16 только `validate_upload`, S17 только polling + `Report` валиден.

## Done-when по сессиям

| Сессия | Done-when |
|---|---|
| S01 | `cd backend && uv run pytest -q`; `/docs` показывает все эндпоинты spec §4 |
| S02 | `cd backend && uv run pytest -q tests/test_fixtures_valid.py` |
| S03 | `cd frontend && npm run build`; каждый маршрут навигации открывается |
| S04 | `cd backend && uv run pytest -q tests/test_parse.py` |
| S05 | `cd backend && LLM_MODE=mock uv run pytest -q tests/test_units.py` |
| S06, S07, S12 | `cd frontend && npm run build` |
| S08 | `cd backend && LLM_MODE=mock uv run pytest -q tests/test_runs.py` |
| S09 | `cd backend && LLM_MODE=mock uv run pytest -q tests/test_functions.py` |
| S10 | `cd backend && LLM_MODE=mock uv run pytest -q tests/test_matching.py` |
| S11 | `cd backend && LLM_MODE=mock uv run pytest -q tests/test_conflicts.py` |
| S13 | `cd backend && uv run pytest -q tests/test_llm_schemas.py` |
| S14 | `cd backend && LLM_MODE=mock uv run pytest -q tests/test_conclusion.py` |
| S15 (руками) | `LLM_MODE=live` demo-run доходит до `done`; фикстуры перезаписаны; затем `LLM_MODE=mock uv run pytest -q` зелёный без ключа |
| S16 | `cd backend && uv run pytest -q tests/test_validation.py` |
| S17 | `cd backend && LLM_MODE=mock uv run pytest -q tests/test_e2e_mock.py`; `deploy/smoke.sh` |
| S18 | второй человек проходит README §8 без ключа и без вопросов |
| S19 | каждая влитая ветка — ровно одна строка в `docs/ai-usage.md` |
| S20 | все ссылки на картинки из README открываются, секретов в кадре нет |

## Команды

```bash
scripts/ops/new-session.sh s/parse codex          # worktree ../wt-parse на ветке от origin/main
scripts/ops/prompt.sh S04                          # промпт в буфер обмена → вставить в окно Codex
scripts/ops/merge-train.sh "s/parse s/units s/runs s/ui-upload s/ui-report"
CHECK="cd backend && uv run pytest -q" scripts/ops/merge-train.sh "..."   # своя проверка вместо make check
scripts/ops/audit.sh prep && scripts/ops/audit.sh save 1530               # S21 аудит, полуручной
ADMISSION_LOOP=1 scripts/ops/admission-check.sh <url>                     # S22 прогон допуска, с 15:30
```

## Честно про пределы

Двадцать сессий на двоих — не двадцать потоков внимания. Работает только потому, что у каждой сессии узкая зона
файлов и команда вместо ревью. Признак переполненной волны: человек не успевает прогнать команды всех своих
сессий до мерж-поезда. Тогда лишняя ветка не мержится и ждёт следующего рейса, а не чинится наспех.
Порядок резки при нехватке времени: S20 → S19-иллюстрации → S17 smoke → S16 таймаут → Cut-if S14 → Cut-if S11.
Ядро S01→S04→S05→S08→S09→S10→S12→S14 не режется.
