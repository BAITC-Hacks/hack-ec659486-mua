"""Образец эндпоинта с вызовом LLM. Скопируйте этот файл для новой фичи.

Паттерн:
  1. Pydantic-модели запроса/ответа и модели ответа LLM — в app/schemas.py.
  2. Промпт — константа в модуле роутера.
  3. llm.complete_json(name=..., schema=strict_schema(Model)) -> dict -> Model.model_validate.
  4. Фикстура для mock-режима — app/mocks/<name>.json (валидная по той же схеме).
  5. Ошибки LLM не ловим здесь: LLMError -> 502 JSON в app.main.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.llm import LLM, get_llm, strict_schema, validate_output
from app.schemas import ExampleLLMOutput, ExampleRequest, ExampleResponse, VersionResponse

router = APIRouter(prefix="/api", tags=["example"])

EXAMPLE_SYSTEM_PROMPT = (
    "Ты — лаконичный ассистент. Отвечай на русском языке одним-двумя предложениями. "
    "Верни строго JSON по заданной схеме."
)


@router.get("/version", response_model=VersionResponse)
def get_version(settings: Annotated[Settings, Depends(get_settings)]) -> VersionResponse:
    return VersionResponse(
        name=settings.app_name,
        version=settings.app_version,
        llm_mode=settings.effective_llm_mode,
    )


@router.post("/example", response_model=ExampleResponse)
def create_example(
    payload: ExampleRequest, llm: Annotated[LLM, Depends(get_llm)]
) -> ExampleResponse:
    """Принимает текст, возвращает структурированный ответ LLM (в mock-режиме — из фикстуры)."""
    data = llm.complete_json(
        name="example",
        system=EXAMPLE_SYSTEM_PROMPT,
        user=payload.text,
        schema=strict_schema(ExampleLLMOutput),
    )
    # Валидируем ответ модели/фикстуры той же моделью, по которой строили схему.
    # validate_output превращает ValidationError в LLMError -> 502, а не в 500.
    output = validate_output(ExampleLLMOutput, data, name="example")
    return ExampleResponse(answer=output.answer, llm_mode=llm.mode)
