# Установка, запуск и проверка — готовый текст для README (разделы 7 и 8)

Зачем отдельный файл. По Положению 5.4.16 и 5.6.5 проект, который не запустился по инструкции
из репозитория, к отбору не допускается, и пояснения потом не принимаются. Эксперт проверяет
без наших ключей (5.6.6) и на своей машине, чаще всего Windows. Поэтому в README:

- только команды, одинаковые на Windows, macOS и Linux: `git`, `docker compose`, `uv`, `npm`, `python`;
- **никаких `make`, `bash`, `sh`, `scripts/*.sh`, `deploy/*.sh`** — у эксперта их может не быть;
- где синтаксис отличается, две строки: bash (macOS, Linux, Git Bash) и Windows PowerShell;
- у каждого шага дословно написано, что должно появиться на экране.

S18 вставляет текст ниже в README как есть, заменяя `<...>` фактами со сдаваемого SHA.
Проверено 23.09 на ноутбуке A (Ubuntu, Docker 29.1, Compose v2.40): оба пути запуска дают
`/health` с `"llm_mode":"mock"` и страницу на порту 3000.

---

## 7. Установка и запуск

### 7.1. Системные требования

| Что | Версия | Зачем |
|---|---|---|
| Git | любая современная | клонировать репозиторий |
| Docker с Compose v2 | Docker Desktop 4.x (Windows, macOS) или Docker Engine 24+ с плагином compose 2.24+ (Linux) | основной способ запуска |
| Свободные порты | 3000 (интерфейс) и 8000 (API) | если заняты — см. 7.6 |
| Память и диск | ~2 ГБ ОЗУ на сборку, ~2 ГБ диска под образы | |
| Без Docker | uv 0.4+ (Python 3.12 он скачает сам), Node.js 20+ (проверено на 22 и 24) | запасной способ, см. 7.5 |

Проверить, что Docker готов: `docker --version` и `docker compose version` печатают версии.
Ключ OpenAI для проверки **не нужен**: по умолчанию проект работает в режиме `mock`,
ответы языковой модели берутся из фикстур в репозитории, и это видно в `/health` и в шапке интерфейса.

### 7.2. Клонирование

```
git clone <URL репозитория>
cd <папка репозитория>
```

### 7.3. Настройки окружения

Файл `.env` необязателен: без него проект стартует в режиме `mock`. Чтобы что-то поменять,
скопируйте пример и правьте значения:

- bash, zsh, Git Bash: `cp .env.example .env`
- Windows PowerShell: `Copy-Item .env.example .env`
- Windows cmd: `copy .env.example .env`

| Переменная | По умолчанию | Назначение | Обязательна |
|---|---|---|---|
| `LLM_MODE` | `mock` | `mock` — ответы из фикстур, ключ не нужен; `live` — реальные вызовы OpenAI. Только явно, тихого переключения нет | нет |
| `OPENAI_API_KEY` | пусто | ключ OpenAI | только при `LLM_MODE=live` |
| `OPENAI_MODEL` | `gpt-5.6-luna` | модель Responses API | нет |
| `CORS_ORIGINS` | `http://localhost:3000` | адреса интерфейса, которым разрешён доступ к API | нет |
| `APP_VERSION` | `0.1.0` | версия в `/health` | нет |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | адрес API для браузера | нет |
| `NEXT_PUBLIC_APP_NAME` | `ОргДифф` | название в шапке | нет |
| `DOMAIN` | пусто | только для развёртывания на сервере | нет |
| `NVIDIA_API_KEY` | пусто | запасной провайдер, по желанию | нет |

### 7.4. Запуск через Docker (основной способ)

```
docker compose up --build
```

Первый запуск собирает образы; на нашей машине это заняло `<N>` минут (замер, не обещание).
Готово, когда в логе есть строка `Application startup complete` от backend и `Ready` от frontend.

- Интерфейс: http://localhost:3000
- API и документация: http://localhost:8000/docs
- Состояние: http://localhost:8000/health

Остановить: `Ctrl+C`, затем `docker compose down`.

### 7.5. Запуск без Docker (запасной способ, две вкладки терминала)

Установить uv, если его нет:

- Windows: `winget install --id=astral-sh.uv -e`
- macOS: `brew install uv`
- любая ОС с Python: `python -m pip install uv`

После установки открыть новое окно терминала. Проверка: `uv --version`, `node --version` (20 и выше).

Вкладка 1, API (Python 3.12 uv скачает сам при первом `uv sync`):

```
cd backend
uv sync
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Ожидаемо: строка `Application startup complete`, а http://localhost:8000/health в браузере показывает
`{"status":"ok","llm_mode":"mock",...}`. Настройки backend берёт из `.env` в корне репозитория автоматически.

Вкладка 2, интерфейс:

```
cd frontend
npm ci
npm run dev
```

Ожидаемо: строка `Ready`, а http://localhost:3000 открывается, в шапке «ОргДифф» и метка режима `mock`.
Адрес API по умолчанию `http://localhost:8000`, менять ничего не нужно.

### 7.6. Если порты 3000 или 8000 заняты

Без Docker запустите на других портах (пример: API на 18000, интерфейс на 13000).

Вкладка 1, bash:

```
cd backend
CORS_ORIGINS=http://localhost:13000 uv run uvicorn app.main:app --host 127.0.0.1 --port 18000
```

Вкладка 1, Windows PowerShell:

```
cd backend
$env:CORS_ORIGINS="http://localhost:13000"; uv run uvicorn app.main:app --host 127.0.0.1 --port 18000
```

Вкладка 2, bash:

```
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:18000 npm run dev -- -p 13000
```

Вкладка 2, Windows PowerShell:

```
cd frontend
$env:NEXT_PUBLIC_API_URL="http://localhost:18000"; npm run dev -- -p 13000
```

Дальше всё как в 7.5, только адреса http://localhost:13000 и http://localhost:18000/health.
Через Docker порты заданы в `docker-compose.yml` (`"3000:3000"`, `"8000:8000"`): поменяйте левое число,
впишите новые адреса в `NEXT_PUBLIC_API_URL` и `CORS_ORIGINS` в `.env` и снова `docker compose up --build`.

### 7.7. Режим live (по желанию, нужен свой ключ OpenAI)

В `.env` укажите `OPENAI_API_KEY=<ключ>` и `LLM_MODE=live`, затем перезапустите
(`docker compose up --build` или команды из 7.5). В `/health` появится `"llm_mode":"live"`.
Если `LLM_MODE=live`, а ключ пуст, приложение не стартует и печатает, что исправить: тихой подмены режима нет.

### 7.8. Типичные ошибки

| Что видно | Что сделать |
|---|---|
| `port is already allocated` или `EADDRINUSE` | порт занят — раздел 7.6 |
| `LLM_MODE=live, но OPENAI_API_KEY пуст` | поставить `LLM_MODE=mock` в `.env` или вписать ключ |
| `docker: 'compose' is not a docker command` | установлен старый docker-compose v1; нужен Docker Desktop 4.x или плагин Compose v2 |
| `Cannot connect to the Docker daemon` | запустить Docker Desktop (Windows, macOS) или службу docker (Linux) |
| `uv: command not found` после установки | открыть новое окно терминала; либо `python -m pip install uv` |
| в интерфейсе «API недоступен» | проверить, что http://localhost:8000/health отвечает; при других портах — 7.6 |

---

## 8. Как проверить решение (сценарий для жюри, без ключа и аккаунтов)

Предусловие: выполнен раздел 7.4 или 7.5, `LLM_MODE` не менялся (значит `mock`).

1. Открыть http://localhost:8000/health. Ожидаемо ровно:
   `{"status":"ok","llm_mode":"mock","model":"<OPENAI_MODEL из .env>","version":"0.1.0"}`.
2. Открыть http://localhost:3000. Ожидаемо: шапка «ОргДифф», метка режима `mock`, состояние API «ok».
3. `<продуктовый шаг 1: страница → действие → ожидаемый экран дословно>`
4. `<продуктовый шаг 2>`
5. `<... до результата основного сценария; входной файл для вставки — из data/samples/, чтобы жюри не придумывало свой>`

В режиме `mock` ответы языковой модели берутся из фикстур в репозитории и помечены в интерфейсе.
Что меняется с ключом: раздел 7.7; сценарий тот же, ответы генерируются моделью.

Автотесты, по желанию:

```
cd backend
uv run pytest -q
```

Ожидаемо: `<N> passed` (число — со сдаваемого SHA, не из головы). Интерфейс: `cd frontend`, затем
`npm run build` завершается без ошибок.
