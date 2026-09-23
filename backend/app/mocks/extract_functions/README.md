# Mock-фикстуры `extract_functions` (S09)

Файл `<hash>.json` — ответ на один вызов `extract_functions`, где
`hash = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True))[:16]`, а `payload` —
вход модели из `app.functions.build_payload` (`{version, unit, clauses}`). Нет файла для входа —
`LLMError` с именем ожидаемого файла (в mock-режиме свои документы не анализируются).

**Происхождение смешанное.** S15 записала ответы модели для итогового demo-run
(коммит `bb7ddd3`, [отчёт](../../../../status/agents/S15.md)). Исторические тестовые
входы ниже остаются черновыми; их нельзя выдавать за ответы модели.

Первоначальные файлы S09 сгенерированы правилами
`draft_fixtures.py` (см. его docstring) по разделам 2, 4 и 5 редакций 8 и 9 тестового комплекта:
по одному файлу на подразделение-владельца пунктов (`extract_all` с подразделениями S05) и по
одному на весь документ (`extract_functions(doc, None)`). Формат — как у живого ответа
(`ExtractFunctionsOut`), для отдельной записи ответов без правки кода использовалась команда:

```bash
cd backend && LLM_MODE=live LLM_RECORD_MOCKS=1 uv run python -m app.functions \
  "../data/case11/Положение_о_внутреннем_аудите_редакция_8_обезличено.docx" \
  "../data/case11/Положение_о_внутреннем_аудите_редакция_9_обезличено.docx"
```

Перегенерировать черновые (после изменения парсера S04, подразделений S05 или выбора пунктов):

```bash
cd backend && LLM_MODE=mock uv run python -m app.mocks.extract_functions.draft_fixtures
```
