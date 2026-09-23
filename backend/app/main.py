"""Точка входа FastAPI: CORS, роутеры, /health и единый JSON-формат ошибок.

Запуск: uvicorn app.main:app --reload
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.llm import LLMError, redact_secrets
from app.routers import example, runs

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "LLM mode: %s (model=%s), version=%s",
        settings.effective_llm_mode,
        settings.openai_model,
        settings.app_version,
    )
    yield


def create_app() -> FastAPI:
    """Фабрика приложения (удобно для тестов: настройки читаются при создании)."""
    settings = get_settings()
    settings.check_startup()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "ОргДифф: сравнение оргструктуры и функционала по документам «до» и «после» "
            "реорганизации. Контракт — app/schemas.py (зеркало frontend/lib/types.ts); "
            "ошибки — {error, detail}."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Роутеры фич: по одному модулю в app/routers/, подключать здесь.
    # После волны 1 (S01) файл закрыт: новые роутеры не добавляются, логика — в своих модулях.
    app.include_router(example.router)
    app.include_router(runs.router)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        current = get_settings()
        return {
            "status": "ok",
            "llm_mode": current.effective_llm_mode,
            "model": current.openai_model,
            "version": current.app_version,
        }

    # --- Единый формат ошибок: {"error": "<код>", "detail": ...} ---------------------------

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "detail": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Роутер может задать свой код ошибки и русский текст: detail={"error": ..., "detail": ...}
        # (см. app.routers.runs.api_error). Иначе — общий код http_error.
        detail = exc.detail
        if isinstance(detail, dict) and "error" in detail and "detail" in detail:
            content = {"error": str(detail["error"]), "detail": detail["detail"]}
        else:
            content = {"error": "http_error", "detail": detail}
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=getattr(exc, "headers", None),
        )

    # Клиенту — постоянный текст и короткий ref для сопоставления с логом.
    # Подробности остаются на сервере: тело исключения провайдера может содержать
    # ключ, фрагмент запроса или внутренние пути.

    @app.exception_handler(LLMError)
    async def llm_exception_handler(_: Request, exc: LLMError) -> JSONResponse:
        ref = uuid4().hex[:8]
        logger.error("LLM error [%s] %s: %s", ref, type(exc).__name__, redact_secrets(str(exc)))
        return JSONResponse(
            status_code=502,
            content={
                "error": "llm_error",
                "detail": "Языковая модель сейчас недоступна. Повторите попытку.",
                "ref": ref,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        ref = uuid4().hex[:8]
        # Не logger.exception: трейсбек печатает текст исключения целиком, и секрет
        # внутри него попал бы в лог, а лог попадает в скриншоты и запись экрана.
        logger.error(
            "Необработанная ошибка [%s] %s: %s",
            ref,
            type(exc).__name__,
            redact_secrets(str(exc)),
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "detail": "Внутренняя ошибка сервера.",
                "ref": ref,
            },
        )

    return app


app = create_app()
