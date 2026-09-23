# Mock-фикстуры LLM

Используются, когда `LLM_MODE=mock` или `OPENAI_API_KEY` пуст (см. `app/llm.py`).

## Именование

| Вызов                                         | Файл фикстуры        |
| --------------------------------------------- | -------------------- |
| `llm.complete_json(name="example", ...)`      | `example.json`       |
| `llm.complete_json(name="risk_report", ...)`  | `risk_report.json`   |
| `llm.complete_text(..., name="summary")`      | `summary.txt`        |
| `llm.complete_text(...)` (name по умолчанию)  | `text.txt`           |

`name` — только `[A-Za-z0-9_-]`. Нет файла → `LLMError("no mock fixture for <name>")` → HTTP 502.

## Правила

- JSON-фикстура должна проходить ту же Pydantic-модель, что и живой ответ
  (`Model.model_validate(data)` в роутере) — иначе mock-режим будет отличаться от live.
- Делайте фикстуры реалистичными и на русском: жюри увидит именно их, если ключа нет.
- Один вызов — одна фикстура. Если для разных входов нужны разные ответы, заведите
  разные `name` (например `plan_short`, `plan_full`) или выбирайте фикстуру в роутере.
