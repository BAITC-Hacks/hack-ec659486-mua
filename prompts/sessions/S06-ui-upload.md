# S06 — Страница загрузки (волна 2, 14:40–15:20, B, ветка `s/ui-upload`)

Прочитай `AGENTS.md`, `docs/case.md`, `docs/spec-case11.md` §1 (шаги 1–2), §4, §6; `frontend/lib/api.ts` (хелпер `api<T>`, `ApiError`), `frontend/lib/types.ts` (`RunCreated`, `RunStatus`, `Report`), `frontend/components/ui/*` (button, card, spinner, empty-state), `frontend/app/page.tsx` из `origin/s/ui-shell` (заглушка, которую ты заменяешь).

**Пишешь только в:** `frontend/app/page.tsx`, `frontend/components/upload-box.tsx`, `frontend/lib/api-runs.ts`.
**Не трогаешь:** `layout.tsx`, `lib/api.ts`, `lib/types.ts`, `lib/fixtures/`, страницы `runs/[id]` и `report/[id]`, бэкенд.

Задача: первый экран демо-пути — пользователь загружает документы «до» и «после» или берёт тестовый комплект и попадает на страницу прогресса.

Сделай:
1. `frontend/lib/api-runs.ts` — тонкие обёртки над `api<T>` из `lib/api.ts`, без своего `fetch`: `createRun(before: File[], after: File[]): Promise<RunCreated>` (POST `/api/runs`, `FormData` с полями `before[]` и `after[]`, по одному `append` на файл; `Content-Type` не ставить — хелпер это учитывает), `createDemoRun(): Promise<RunCreated>` (POST `/api/runs/demo`, пустое тело), `getRun(id): Promise<RunStatus>` (GET `/api/runs/{id}`, `cache: "no-store"`), `getReport(id): Promise<Report>` (GET `/api/runs/{id}/report`). Типы только из `lib/types.ts`.
2. `frontend/components/upload-box.tsx` — клиентский компонент: подпись («До реорганизации» / «После реорганизации»), `<input type="file" multiple accept=".docx">`, зона перетаскивания на нативных `onDragOver`/`onDrop`, список выбранных файлов с размером и кнопкой «убрать». Проверка на клиенте до отправки: только `.docx`, ≤ 10 файлов на зону, ≤ 10 МБ каждый — иначе понятный текст ошибки под зоной, файл не добавляется. Пропсы: `label`, `files`, `onChange`, `disabled`.
3. `frontend/app/page.tsx` — две `UploadBox` (до/после), кнопка «Проанализировать» (активна, когда в каждой зоне ≥ 1 файл) → `createRun` → `router.push("/runs/" + run_id)`; кнопка «Тестовый комплект» с пояснением «редакции 8 и 9 Положения о внутреннем аудите» → `createDemoRun` → тот же переход. Пока запрос идёт — спиннер и обе кнопки заблокированы. Ошибка `ApiError` показывается текстом `message` (в нём уже русский `detail` бэкенда); при `status === 0` добавь подсказку «запущен ли backend на :8000». Ничего не выдумывай: нет прогресса, нет отчёта — только переход.
4. Никаких сторонних библиотек для drag-and-drop и форм; только `next`, `react`, Tailwind и `components/ui`. Русские подписи, пустые состояния и ошибки — на русском.

**Done-when:** `cd frontend && npm run build`
**Cut-if:** drag-and-drop убрать, оставить только `<input type="file">`; список файлов — простыми именами без кнопки «убрать».

В конце выведи список изменённых файлов и вывод Done-when.

---

## Режим работы: автономно, до зелёного Done-when

Ты работаешь в GUI, человек к тебе не вернётся до отчёта. Рабочая папка — worktree ветки `s/ui-upload`.
Порядок: реализуй → **сам выполни команду Done-when** → красная: почини и повтори (до трёх попыток) →
зелёная: `git add -A && git commit -m "feat(S06): <что сделано>" && git push -u origin s/ui-upload`.
Затем создай `status/agents/S06.md` в этом worktree: первая строка `# S06 — ЗЕЛЕНО` или `# S06 — КРАСНО`,
далее команда Done-when и её вывод, список изменённых файлов, что не сделано и почему; закоммить и запушь его так же.
Запреты: не пушить и не мержить в `main`; не трогать файлы вне своей строки матрицы владения; не добавлять зависимости;
не переписывать README и чужие тесты. После трёх красных попыток — отчёт «КРАСНО» с выводом ошибки и остановись.
