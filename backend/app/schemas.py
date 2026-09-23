"""Pydantic-контракты API. Зеркало на фронтенде: frontend/lib/types.ts."""

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Единый формат ошибок API (см. обработчики в app.main)."""

    error: str = Field(description="Машиночитаемый код ошибки", examples=["validation_error"])
    detail: object | None = Field(default=None, description="Подробности (строка или список)")


class VersionResponse(BaseModel):
    name: str
    version: str
    llm_mode: str = Field(description="Фактический режим LLM: live или mock")


# --- Пример эндпоинта /api/example ---------------------------------------------------------


class ExampleRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000, description="Произвольный текст пользователя")


class ExampleLLMOutput(BaseModel):
    """Схема структурированного ответа LLM.

    Используется и для JSON Schema (strict_schema), и для валидации ответа/фикстуры.
    Для strict-режима Structured Outputs все поля должны быть обязательными.

    extra="forbid" обязателен: strict_schema ставит additionalProperties=false в схему
    для провайдера, но обычный BaseModel лишнее поле молча отбрасывал — локальная
    проверка была слабее заявленной. Все схемы ответов LLM объявлять так же.
    """

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(description="Краткий ответ на текст пользователя")


class ExampleResponse(BaseModel):
    answer: str
    llm_mode: str
