# S12 — Фронт на живом API (волна 3, 15:20–16:00, B, ветка `s/ui-wire`)

Прочитай `AGENTS.md`, `docs/case.md` (условие 4 — источник у каждого вывода), `docs/spec-case11.md` §1 (шаги 2–4), §4, §6; `frontend/lib/api.ts` (`api<T>`, `ApiError`), `frontend/lib/types.ts` (`RunStatus`, `Report`, `Clause`, `Source`), `frontend/lib/api-runs.ts` (S06: `getRun`, `getReport`), `frontend/app/report/[id]/page.tsx` из S07 (фикстура + заглушка `SourceDrawer` с пропсами `{ source, onClose }`), `frontend/app/runs/[id]/page.tsx` из S03 (заглушка, которую ты заменяешь). Если чего-то нет в ветке — `git fetch origin s/ui-upload s/ui-report && git show origin/<ветка>:<путь>`, но чужие файлы не правь.

**Пишешь только в:** `frontend/app/runs/[id]/page.tsx`, `frontend/components/run-progress.tsx`, `frontend/components/source-drawer.tsx`, `frontend/lib/api-runs.ts` (только расширить), `frontend/app/report/[id]/page.tsx` (только замена источника данных и импорт `SourceDrawer`).
**Не трогаешь:** `layout.tsx`, `lib/api.ts`, `lib/types.ts`, `lib/fixtures/`, `page.tsx` загрузки, таблицы отчёта (`units-table`, `function-matrix`, `duplicates-list`, `conflicts-list`, `conclusion-view`), `ui/*`, бэкенд.

Задача: демо-путь целиком на поднятом бэкенде — «Тестовый комплект» → прогресс по шагам → отчёт с живыми данными → клик по «п. N» открывает текст пункта из документа.

Сделай:
1. `lib/api-runs.ts`: добавь `getClause(runId, docId, clauseNumber): Promise<Clause>` — GET `/api/runs/{id}/clauses/{doc_id}/{clause_number}` через `api<T>`, `cache: "no-store"`, `encodeURIComponent` для сегментов. Свой `fetch` не пиши. Добавь `useFixtures(): boolean` — `process.env.NEXT_PUBLIC_USE_FIXTURES === "1"`.
2. `components/run-progress.tsx`: пропсы `{ status: RunStatus }`; семь шагов «Разбор → Подразделения → Функции → Кандидаты → Проверка → Конфликты → Заключение», соответствие статусов `parsing/units/functions/candidates/verification/conflicts/conclusion` (ровно spec §4), `queued` — «в очереди»; пройденные, текущий (спиннер) и будущие шаги визуально различимы; полоса `progress` в процентах. `error` — красный блок с текстом `status.error` как есть (там уже русский текст бэкенда), ничего не дописывай.
3. `app/runs/[id]/page.tsx`: клиентская страница, `getRun(id)` сразу и затем каждые 2 с через `setInterval` с очисткой в `useEffect`; при `done` — `router.replace("/report/" + id)`; при `error` — опрос остановить, показать `RunProgress` с ошибкой и ссылку «Загрузить заново» на `/`. `ApiError` показывать текстом `message`; при `status === 0` — подсказка «запущен ли backend на :8000», опрос продолжать. Первый рендер — спиннер «Запрашиваем статус…».
4. `components/source-drawer.tsx`: пропсы `{ runId, source: Source | null, onClose }`. При открытии — `getClause(runId, source.doc_id, source.clause_number)`; пока грузится — `source.quote` и спиннер; успех — `doc_name`, версия «до»/«после», раздел `section`, номер, полный `text`; ошибка — `quote` из источника и текст ошибки «полный текст пункта недоступен: …». Кнопка «Закрыть», закрытие по Escape. Ничего не придумывать: нет `text` — показываем только цитату.
5. `app/report/[id]/page.tsx`: вместо фикстуры — `getReport(id)` в `useEffect`; фикстура остаётся только при `useFixtures()` или `id === "demo"` без бэкенда (`ApiError.status === 0`) — с пометкой «показана демонстрационная фикстура». 404 «отчёт ещё не готов» — ссылка на `/runs/{id}`. Заглушку `SourceDrawer` из S07 удалить, подключить новый компонент; остальная разметка вкладок без изменений.
6. Все подписи и ошибки на русском; только `next`, `react`, Tailwind и `components/ui`.

**Done-when:** `cd frontend && npm run build`
**Cut-if:** закрытие по Escape; пометка про фикстуру; полоса прогресса — только текст «N %».

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/ui-wire`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S12): <что сделано>" && git push -u origin s/ui-wire`.
Затем создай `status/agents/S12.md` в этом worktree: первая строка `# S12 — ЗЕЛЕНО` или `# S12 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
