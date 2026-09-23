"""Тонкая обёртка над OpenAI Responses API с честным mock-режимом.

Использование в роутере:

    llm = LLM(get_settings())
    data = llm.complete_json(
        name="example",
        system="Ты ассистент...",
        user=payload.text,
        schema=strict_schema(ExampleLLMOutput),
    )

Режим задаётся только явно через LLM_MODE. В mock-режиме ответ читается из
app/mocks/<name>.json (для complete_json) или app/mocks/<name>.txt (для complete_text).
Отсутствие фикстуры — это ошибка (LLMError), а не тихая подмена.
LLM_MODE=live без ключа не превращается в mock: приложение не стартует (Settings.check_startup).
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

MOCKS_DIR = Path(__file__).resolve().parent / "mocks"
MAX_ATTEMPTS = 2  # одна повторная попытка при транзиентной ошибке
RETRY_DELAY_SECONDS = 1.0
# Бюджет одного вызова. Держать согласованным с таймаутом фронта в docs/spec.md §7:
# худший случай одного запроса = MAX_ATTEMPTS * REQUEST_TIMEOUT_SECONDS + RETRY_DELAY_SECONDS.
REQUEST_TIMEOUT_SECONDS = 40.0
_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
# Ключи провайдеров в тексте исключений: не должны попадать ни в лог, ни в ответ клиенту.
_SECRET_RE = re.compile(r"\b(sk|rk|pk)-[A-Za-z0-9_\-]{6,}", re.IGNORECASE)


def redact_secrets(text: str) -> str:
    """Заменяет похожее на API-ключ на «***». Лог может попасть в скриншот или запись экрана."""
    return _SECRET_RE.sub("***", text)


def validate_output(model: type[BaseModel], data: dict[str, Any], name: str = "output") -> Any:
    """Валидирует ответ модели её же схемой и превращает провал в LLMError.

    Без этого ValidationError долетает до общего обработчика и становится 500:
    невалидный ответ провайдера — это 502, ошибка внешней системы, а не наша.
    """
    from pydantic import ValidationError

    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise LLMError(
            f"Ответ LLM не соответствует схеме '{name}': {exc.error_count()} ошибок"
        ) from exc


class LLMError(Exception):
    """Ошибка обращения к LLM: сеть, лимиты, невалидный JSON, отказ модели, нет mock-фикстуры."""


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema Pydantic-модели, приведённая к требованиям strict Structured Outputs.

    Для каждого объекта: additionalProperties=false и все properties в required.
    Вложенные модели ($defs) обрабатываются рекурсивно.
    """
    schema = model.model_json_schema()
    _make_strict(schema)
    return schema


def _make_strict(node: Any) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object" and isinstance(node.get("properties"), dict):
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())
        for value in node.values():
            _make_strict(value)
    elif isinstance(node, list):
        for item in node:
            _make_strict(item)


def _is_transient(exc: Exception) -> bool:
    """Сетевые ошибки, таймауты, 429 и 5xx — имеет смысл повторить один раз."""
    try:
        from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
    except ImportError:  # pragma: no cover - openai всегда в зависимостях
        return False
    transient = APIConnectionError | APITimeoutError | InternalServerError | RateLimitError
    return isinstance(exc, transient)


def _extract_refusal(response: Any) -> str | None:
    """Structured Outputs могут вернуть refusal вместо JSON — достаём текст отказа."""
    for item in getattr(response, "output", None) or []:
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "refusal":
                return getattr(part, "refusal", None) or "модель отказалась отвечать"
    return None


class LLM:
    """Единая точка вызова LLM. Создаётся на запрос (дёшево: клиент OpenAI ленивый)."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any = None

    @property
    def mode(self) -> str:
        return self.settings.effective_llm_mode

    # --- public API ---------------------------------------------------------------------

    def complete_json(
        self, name: str, system: str, user: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        """Структурированный ответ по JSON Schema. name — имя схемы и mock-фикстуры."""
        _validate_name(name)
        if self.mode == "mock":
            return self._load_mock_json(name)

        raw = self._create(
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": name,
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM вернула невалидный JSON для '{name}': {exc}") from exc
        if not isinstance(data, dict):
            raise LLMError(f"LLM вернула не JSON-объект для '{name}'")
        return data

    def complete_text(self, system: str, user: str, *, name: str = "text") -> str:
        """Свободный текстовый ответ. name — имя mock-фикстуры app/mocks/<name>.txt."""
        _validate_name(name)
        if self.mode == "mock":
            return self._load_mock_text(name)
        raw = self._create(
            input=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return raw.strip()

    # --- live ---------------------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:  # pragma: no cover
                raise LLMError("Пакет openai не установлен") from exc
            # Повторы делаем сами (MAX_ATTEMPTS), поэтому у SDK max_retries=0.
            self._client = OpenAI(
                api_key=self.settings.openai_api_key,
                timeout=REQUEST_TIMEOUT_SECONDS,
                max_retries=0,
            )
        return self._client

    def _create(self, **kwargs: Any) -> str:
        """Вызов Responses API с одной повторной попыткой. Возвращает output_text."""
        client = self._get_client()
        model = self.settings.openai_model
        response: Any = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = client.responses.create(model=model, **kwargs)
                break
            except Exception as exc:
                if attempt < MAX_ATTEMPTS and _is_transient(exc):
                    logger.warning(
                        "LLM: транзиентная ошибка (%s), повтор через %.0f с",
                        type(exc).__name__,
                        RETRY_DELAY_SECONDS,
                    )
                    time.sleep(RETRY_DELAY_SECONDS)
                    continue
                # Текст исключения провайдера может содержать ключ и уходит в лог
                # уже очищенным; наружу отдаём только тип.
                logger.error(
                    "LLM: запрос не удался (%s): %s", type(exc).__name__, redact_secrets(str(exc))
                )
                raise LLMError(f"Запрос к LLM не удался ({type(exc).__name__})") from exc

        refusal = _extract_refusal(response)
        if refusal:
            raise LLMError(f"LLM отказалась выполнять запрос: {refusal}")

        # incomplete приходит и с непустым output_text (обрыв по лимиту токенов);
        # без этой проверки обрезанный JSON выглядел бы как валидный ответ.
        status = getattr(response, "status", None)
        if status is not None and status != "completed":
            raise LLMError(f"LLM не завершила ответ (status={status})")

        text = getattr(response, "output_text", "") or ""
        if not text:
            raise LLMError(f"LLM вернула пустой ответ (status={status})")
        return text

    # --- mock ---------------------------------------------------------------------------

    def _load_mock_json(self, name: str) -> dict[str, Any]:
        path = MOCKS_DIR / f"{name}.json"
        if not path.is_file():
            raise LLMError(f"no mock fixture for '{name}' (ожидался файл {path})")
        with path.open(encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError as exc:
                raise LLMError(f"Mock-фикстура {path} содержит невалидный JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise LLMError(f"Mock-фикстура {path} должна содержать JSON-объект")
        logger.debug("LLM mock: %s", path.name)
        return data

    def _load_mock_text(self, name: str) -> str:
        path = MOCKS_DIR / f"{name}.txt"
        if not path.is_file():
            raise LLMError(f"no mock fixture for '{name}' (ожидался файл {path})")
        logger.debug("LLM mock: %s", path.name)
        return path.read_text(encoding="utf-8").strip()


def _validate_name(name: str) -> None:
    if not _NAME_RE.fullmatch(name):
        raise LLMError(f"Недопустимое имя схемы/фикстуры: {name!r} (разрешены [A-Za-z0-9_-])")


def get_llm() -> LLM:
    """FastAPI-зависимость: LLM с текущими настройками."""
    return LLM(get_settings())
