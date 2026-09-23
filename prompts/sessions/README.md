# Лист запуска по волнам — кейс 11 «ОргДифф», старт 14:15

Сейчас 14:10, кодинг до 18:00, **freeze 17:15**, сдача 17:45. Матрица владения и правила — `docs/sessions.md`,
пошаговый runbook — `docs/runbook-gui.md`. Агенты запускаются **только в интерфейсе** (Codex app, Claude Code).

Один порядок действий на каждую автономную сессию:

```bash
scripts/ops/new-session.sh s/<имя> codex   # worktree ../wt-<имя> на ветке от origin/main, печатает путь
scripts/ops/prompt.sh SNN                  # промпт prompts/sessions/SNN-*.md в буфер обмена
```

Дальше — **Codex app** → «Open folder» → путь worktree, который напечатала команда (`../wt-<имя>`) → режим Full access →
вставить промпт из буфера → Enter. Окно не трогать до появления `status/agents/SNN.md` (первая строка ЗЕЛЕНО/КРАСНО).
Красный отчёт — открыть тот же worktree и дожать в диалоге. Интерактивные сессии (S01, S03, S15, S18–S20) —
то же окно, но человек читает вопросы агента и отвечает.

Сессия закрыта, когда зелёная её команда **Done-when**. Не «выглядит готово». Мержит только B через `scripts/ops/merge-train.sh`
из чистого `main` после `git pull --rebase origin main`; порядок веток в команде ниже — не менять.

---

## Волна 1 — 14:15–14:40 — 3 окна

| Время | Кто | Терминал | Codex app | Промпт | Режим |
|---|---|---|---|---|---|
| 14:15 | A | `scripts/ops/new-session.sh s/contract codex` | открыть `../wt-contract` | `scripts/ops/prompt.sh S01` | интерактивно (A1): отвечать по `docs/spec-case11.md` §3–§5 |
| 14:15 | B | `scripts/ops/new-session.sh s/ui-shell codex` | открыть `../wt-ui-shell` | `scripts/ops/prompt.sh S03` | интерактивно (B2) |
| 14:20 | B | `scripts/ops/new-session.sh s/fixtures codex` | второе окно, `../wt-fixtures` | `scripts/ops/prompt.sh S02` | автономно, через 5 минут после S01 (схемы уже появляются в `origin/s/contract`) |
| 14:25 | A | Claude Code в корне репо команды | — | `scripts/ops/prompt.sh timekeeper`, затем `/loop 20m` | штурман A3 |
| 14:35 | оба | читать `status/agents/S01.md`, `S02.md`, `S03.md` | | | |

Мерж-поезд 14:40 (B):

```bash
git pull --rebase origin main
scripts/ops/merge-train.sh "s/contract s/fixtures s/ui-shell"
git tag green-1440 && git push --tags && git push origin main
```

## Волна 2 — 14:40–15:20 — 5 автономных окон

| Кто | Терминал | Codex app | Промпт |
|---|---|---|---|
| A | `scripts/ops/new-session.sh s/parse codex` | `../wt-parse` | `scripts/ops/prompt.sh S04` |
| A | `scripts/ops/new-session.sh s/units codex` | `../wt-units` | `scripts/ops/prompt.sh S05` |
| A | `scripts/ops/new-session.sh s/runs codex` | `../wt-runs` | `scripts/ops/prompt.sh S08` |
| B | `scripts/ops/new-session.sh s/ui-upload codex` | `../wt-ui-upload` | `scripts/ops/prompt.sh S06` |
| B | `scripts/ops/new-session.sh s/ui-report codex` | `../wt-ui-report` | `scripts/ops/prompt.sh S07` |

Окно A1 (`wt-contract`) остаётся открытым для вопросов о контракте; окно B2 (`wt-ui-shell`) — для правок вида после мержа.
15:00 — чекины; 15:10 — читать отчёты `status/agents/S04,S05,S08,S06,S07.md`, красное дожимать.

Мерж-поезд 15:20 (B) — бэкенд-данные (parse) → модель (units) → роутеры (runs) → фронт:

```bash
git pull --rebase origin main
scripts/ops/merge-train.sh "s/parse s/units s/runs s/ui-upload s/ui-report"
git tag green-1520 && git push --tags && git push origin main
```

## Волна 3 — 15:20–16:00 — 5 автономных окон

| Кто | Терминал | Codex app | Промпт |
|---|---|---|---|
| A | `scripts/ops/new-session.sh s/functions codex` | `../wt-functions` | `scripts/ops/prompt.sh S09` |
| A | `scripts/ops/new-session.sh s/matching codex` | `../wt-matching` | `scripts/ops/prompt.sh S10` |
| A | `scripts/ops/new-session.sh s/conflicts codex` | `../wt-conflicts` | `scripts/ops/prompt.sh S11` |
| B | `scripts/ops/new-session.sh s/ui-wire codex` | `../wt-ui-wire` | `scripts/ops/prompt.sh S12` |
| B | `scripts/ops/new-session.sh s/schemas codex` | `../wt-schemas` | `scripts/ops/prompt.sh S13` |
| фон | `ADMISSION_LOOP=1 scripts/ops/admission-check.sh <url репо>` с 15:30 (скрипт, агент не нужен) | | |

15:40 — чекины; 15:50 — отчёты `S09,S10,S11,S12,S13.md`.

Мерж-поезд 16:00 (B) — схемы LLM → модули шагов → фронт:

```bash
git pull --rebase origin main
scripts/ops/merge-train.sh "s/schemas s/functions s/matching s/conflicts s/ui-wire"
git tag green-1600 && git push --tags && git push origin main
```

**16:00 — контрольная точка.** `docker compose up --build` → «Тестовый комплект» → прогресс → отчёт с четырьмя вкладками
в mock-режиме. Не работает — волна 4 режется до Cut-if (см. `docs/sessions.md`).

## Волна 4 — 16:00–16:40 — 3 автономных + S15 руками

| Кто | Терминал | Codex app | Промпт |
|---|---|---|---|
| A | `scripts/ops/new-session.sh s/conclusion codex` | `../wt-conclusion` | `scripts/ops/prompt.sh S14` |
| A | `scripts/ops/new-session.sh s/live-fixtures claude` | **S15 руками** (Claude Code или терминал в `../wt-live-fixtures`): вписать ключ в `.env` этого worktree, `LLM_MODE=live`, прогнать demo-run (`POST /api/runs/demo` → `done`), сохранить реальные ответы модели в `backend/app/mocks/*/<hash>.json` поверх ручных фикстур S05/S09–S11; `mocks/write_conclusion/` — только после ЗЕЛЕНО S14; затем `LLM_MODE=mock uv run pytest -q` без ключа; `.env` с ключом не коммитить | промпта нет; в отчёте `status/agents/S15.md` — какие фикстуры реальные |
| B | `scripts/ops/new-session.sh s/validation codex` | `../wt-validation` | `scripts/ops/prompt.sh S16` |
| B | `scripts/ops/new-session.sh s/e2e codex` | `../wt-e2e` | `scripts/ops/prompt.sh S17` |

16:20 — чекины; 16:30 — отчёты `S14,S16,S17.md` и `S15.md`.

Мерж-поезд 16:40 (B) — модель (conclusion) → данные, зависящие от неё (live-fixtures) → роутеры (validation) → тесты (e2e):

```bash
git pull --rebase origin main
scripts/ops/merge-train.sh "s/conclusion s/live-fixtures s/validation s/e2e"
git tag green-1640 && git push --tags && git push origin main
```

**16:40 — ядро end-to-end.** Дальше новых функций нет: только README, раскрытие, картинки и починка того, что нашёл чистый прогон.

## Волна 5 — 16:40–17:15 — доки, интерактивно

| Кто | Терминал | Codex app | Промпт |
|---|---|---|---|
| B | `scripts/ops/new-session.sh s/readme codex` | `../wt-readme` | `scripts/ops/prompt.sh S18` (интерактивно: агент пишет, B проверяет каждое утверждение командой) |
| B | `scripts/ops/new-session.sh s/img codex` | `../wt-img` (после того как README назвал имена картинок) | `scripts/ops/prompt.sh S20` |
| A | `scripts/ops/new-session.sh s/disclosure codex` | `../wt-disclosure` | `scripts/ops/prompt.sh S19` |
| A | параллельно: чистый прогон на своём ноуте по README-черновику (`git clone` в новую папку, `.env` без ключа, `docker compose up --build`, сценарий §8); ошибки — B одной строкой | | |

17:00 — чекины. Чинится только то, что нашёл чистый прогон, в окне нужной сессии; ветка едет этим же поездом.

Мерж-поезд 17:10 (B) — доки, README последним (он ссылается на картинки):

```bash
git pull --rebase origin main
scripts/ops/merge-train.sh "s/disclosure s/img s/readme"
git tag green-17 && git push --tags && git push origin main
```

## 17:15 — freeze

Остановить петлю прогона допуска (Ctrl-C), аудит не собирать, все окна агентов закрыть (кроме штурмана).
Чистый прогон на теге `green-17` (A), видео 60–90 с и ссылка в README (B), `until git push origin main; do sleep 15; done` в 17:40 (A),
форма сдачи 17:45 (B). После 17:45 `main` не трогать (5.4.13, 5.4.14).

---

## Порядок мерж-поезда

Он не случайный: бэкенд-данные → бэкенд-модель → бэкенд-роутеры → фронт-компоненты → фронт-страницы → тесты → доки.
Поздние ветки видят уже смерженные зависимости. Ветка с красной проверкой снимается с рейса и едет следующим — в `main` не чинится.
Проверка по умолчанию `make check`; если make нет: `CHECK="cd backend && uv run pytest -q && cd ../frontend && npm run build" scripts/ops/merge-train.sh "..."`.

## Если что-то пошло не так

| Симптом | Что делать |
|---|---|
| Две сессии правят один файл | Одну остановить. Смотреть матрицу владения в `docs/sessions.md` |
| Конфликт в `main.py`, `schemas.py`, `types.ts` или `layout.tsx` | Розетки поставлены неполно. Доставить их в `s/contract` / `s/ui-shell` и прогнать заново; модуль, которому не хватило поля, добавляет его у себя и пишет в отчёт |
| Сессия не даёт зелёный Done-when 15 минут | Снять с рейса, взять её Cut-if |
| Лимит Codex у A | Запускать окна с аккаунта B или Claude Code с тем же промптом (`new-session.sh <ветка> claude`) |
| Вердикт прогона допуска «не допущены» | Всё останавливается, чинится только это. По 5.4.16 второго шанса нет |
| Не успеваешь прогнать команды всех своих сессий | Волна переполнена: лишняя ветка ждёт следующего рейса |
| Нет фикстуры в mock-режиме (`LLMError: нет файла mocks/...`) | Хэш payload изменился — S15 перезаписывает фикстуру живым ответом, либо владелец модуля обновляет свою ручную |
