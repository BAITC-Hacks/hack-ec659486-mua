# S15 — Живые фикстуры тестового комплекта (волна 4, 16:00–16:40, A, ветка `s/live-fixtures`, нужен ключ)

Прочитай `AGENTS.md` (правило 3: фикстуры — сохранённые реальные ответы модели; правило 4: секреты только в `.env`),
строки S15 в матрице `docs/sessions.md`, `status/agents/S08.md`, `S10.md`, `S11.md`, `S14.md` (что каждый модуль
пишет в `mocks/` и как), `scripts/ops/demo_run.py`.

**Пишешь только в:** `backend/app/mocks/{extract_units,match_units,extract_functions,verify_matches,confirm_loss,embeddings,verify_duplicates,explain_conflict,write_conclusion}/**`,
`status/agents/S15.md`. Если тест модуля на тестовом комплекте (S05, S09, S10, S11, S14 — владелец A) падает только
потому, что живой ответ отличается от ручной фикстуры, можно поправить ожидание в этом тесте: каждое такое изменение
с причиной — в отчёт.
**Не трогаешь:** код модулей и пайплайна, `schemas.py`, `llm.py`, роутеры, фронт. `.env` уже лежит в корне этого
worktree (в `.gitignore`): ключ не выводи, не копируй и не коммить.

## Когда начинать

Запись имеет смысл только на полном коде: в `main` должны быть волна 3 и `s/conclusion` (S14).

```bash
git fetch origin && git merge origin/main
ls backend/app/llm_schemas.py backend/app/functions.py backend/app/candidates.py backend/app/matching.py \
   backend/app/duplicates.py backend/app/rules/conflicts.py backend/app/conclusion.py backend/app/export_md.py
```

Нет хотя бы одного файла — запись не начинай: в `status/agents/S15.md` напиши «ждёт мержа <чего>», запушь и остановись.

## Задача

Один полный живой прогон тестового комплекта с записью всех ответов модели. После этого тот же прогон в mock-режиме
без обращения к модели доходит до `done`, а тесты зелёные.

1. **Запись.** Около 300 вызовов модели, 10–20 минут. Прогон идёт напрямую через `pipeline.run_pipeline`, без таймаута API:
   `cd backend && LLM_MODE=live LLM_RECORD_MOCKS=1 uv run python ../scripts/ops/demo_run.py`
   Итог должен быть `done`. При `partial` или `error` прочитай `detail`. Если причина в твоей зоне — исправь и повтори
   запись целиком: частичная перезапись даёт несогласованные хэши запросов. Если причина в коде модуля — отчёт КРАСНО
   с выводом.
2. **Проверка на фикстурах:** `cd backend && LLM_MODE=mock uv run python ../scripts/ops/demo_run.py` → `итог: done`,
   в выводе нет «нет mock-фикстуры». Числа (подразделения, функции, подтверждённые потери, дубли, конфликты) — в отчёт.
3. **Тесты:** `cd backend && LLM_MODE=mock uv run pytest -q` — зелёный. Фикстуры под тесты не подгоняй.
4. **Перед коммитом:** `git status backend/app/mocks` — только каталоги из строки «Пишешь только в»;
   `git grep -n 'sk-' -- backend/app/mocks` — пусто; `du -sh backend/app/mocks/embeddings` — размер в отчёт.

**Done-when:** `cd backend && LLM_MODE=mock uv run python ../scripts/ops/demo_run.py` печатает `итог: done`
(код выхода 0) и `cd backend && LLM_MODE=mock uv run pytest -q` зелёный.

**Cut-if:** если к 16:25 `s/conclusion` не влит, запиши всё без заключения. Итог записи будет `partial`
(не хватает «Заключения»), в отчёте напиши об этом прямо; S17 останется с `xfail` до следующего прогона записи.

В конце выведи список изменённых каталогов, выводы шагов 1–3 и что не сделано.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/live-fixtures`.
Порядок: дождись условий из «Когда начинать» → запись → проверка → тесты → зелёная:
`git add backend/app/mocks && git commit -m "feat(S15): live fixtures for the case11 kit" && git push -u origin s/live-fixtures`.
Затем создай `status/agents/S15.md` в этом worktree: первая строка `# S15 — ЗЕЛЕНО` или `# S15 — КРАСНО`,
далее команды и их вывод, числа отчёта, размер фикстур, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки; не добавлять зависимости; не выводить
и не коммитить ключ. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
