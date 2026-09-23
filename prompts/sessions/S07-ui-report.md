# S07 — Страница отчёта на фикстуре (волна 2, 14:40–15:20, B, ветка `s/ui-report`)

Прочитай `AGENTS.md`, `docs/case.md` (обязательные условия 1–5 — это ровно четыре вкладки и источник у каждого вывода), `docs/spec-case11.md` §1 п. 3–4, §3, §6. Типы — `frontend/lib/types.ts` (S01), данные — `frontend/lib/fixtures/report.ts` (S02); если в твоей ветке их нет — `git fetch origin s/contract s/fixtures && git show origin/s/fixtures:frontend/lib/fixtures/report.ts`, но сами файлы не правь. Каркас вкладок и `StatusBadge` — из S03 (`components/ui/tabs.tsx`, `components/status-badge.tsx`), переиспользуй.

**Пишешь только в:** `frontend/app/report/[id]/page.tsx`, `frontend/components/units-table.tsx`, `frontend/components/function-matrix.tsx`, `frontend/components/duplicates-list.tsx`, `frontend/components/conflicts-list.tsx`, `frontend/components/conclusion-view.tsx`.
**Не трогаешь:** `layout.tsx`, `lib/*`, `status-badge.tsx`, `ui/*`, бэкенд. Запросов к API нет — страница рендерит фикстуру; подключение к живому API делает S12.

Задача: эксперт открывает `/report/demo` и видит весь результат анализа с источником у каждой строки — ещё до того, как пайплайн заработал.

Сделай:
1. `page.tsx`: берёт `Report` из фикстуры, показывает `run_id`, документы «до»/«после» и `stats`; четыре вкладки: Подразделения, Функции, Дубли и конфликты, Заключение. Локальное состояние `openSource: Source | null` передаётся во все компоненты как `onSource(source)`; в `FunctionMatrix` — `report.function_matches` и `report.constraints`.
2. Источник везде — одна кнопка `«п. {clause_number}»` (не ссылка), которая вызывает `onSource`. Заглушка `SourceDrawer` внутри `page.tsx`: боковая панель с `doc_name`, версией (до/после), номером пункта и `quote`; кнопка «Закрыть». S12 заменит её на панель с запросом `clauses/{doc_id}/{clause_number}` — интерфейс пропсов `{ source, onClose }` сохрани.
3. `units-table.tsx`: таблица `UnitChange[]` — название до, название после, `StatusBadge` статуса, `note`, кнопки источников. Пустой массив → `EmptyState` «Подразделения не найдены».
4. `function-matrix.tsx`: пропсы `{ matches: FunctionMatch[], constraints: Function[] }`; таблица — функции «до» (`before[]`, все тексты через перенос), функции «после» (`after[]`), вид связи `kind` (один-к-одному / разделена / объединена / частично), подразделение, `StatusBadge` статуса и метка `verification`, `confidence` в процентах, источники всех пунктов обеих сторон; фильтр по статусу (Все / сохранена / изменена / утрачена / новая / перенесена) со счётчиком строк. Строки с `verified: false` — не в общей таблице, а отдельным блоком «Кандидаты в потери — требует проверки» с `note` (причина). Отдельный блок «Ограничения» — список `constraints` (текст, исполнитель, источник), без статуса.
5. `duplicates-list.tsx` и `conflicts-list.tsx`: дубли — пара функций с подразделениями, `similarity`, `verification_note`, источники; `verified: false` — отдельно, с меткой «требует проверки»; конфликты — `title`, `rule_id`, `role_pattern`, `severity`, подразделения, `explanation`, `verification_note`, функции с источниками; непроверенные — так же отдельно. Находку без `sources` не рендерить.
6. `conclusion-view.tsx`: `conclusion_md` как простой markdown (заголовки, списки, абзацы, жирный) без библиотек; кнопка «Скачать заключение (.md)» — `<a href="/api/runs/{run_id}/report.md" download>`.
7. Все подписи на русском, статусы — только через `StatusBadge`. Никаких выдуманных чисел: что не пришло в фикстуре — не показывай.

**Done-when:** `cd frontend && npm run build`
**Cut-if:** фильтр в матрице функций; markdown как `<pre>`; панель источника — `<details>` под таблицей.

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/ui-report`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S07): <что сделано>" && git push -u origin s/ui-report`.
Затем создай `status/agents/S07.md` в этом worktree: первая строка `# S07 — ЗЕЛЕНО` или `# S07 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
