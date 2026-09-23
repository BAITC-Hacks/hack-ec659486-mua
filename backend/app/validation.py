"""Проверка содержимого Word и ограничение времени фонового анализа."""

import asyncio
import logging
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from fastapi.responses import JSONResponse

from app import store
from app.llm import redact_secrets
from app.parse.docx import parse_docx

logger = logging.getLogger(__name__)

MAX_FILES = 10
MAX_BYTES = 10 * 1024 * 1024
PIPELINE_TIMEOUT_S = 180
_WORD_TEXT = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"


class UploadError(Exception):
    """Ошибка конкретного загруженного файла с понятным текстом для пользователя."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(reason)
        self.field = field
        self.reason = reason

    def response(self) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "validation", "detail": f"{self.field}: {self.reason}"},
        )


def validate_docx_content(path: Path, field: str) -> None:
    """Проверяет ZIP, XML, непустой текст и наличие разбираемого номера пункта."""
    path = Path(path)
    try:
        with zipfile.ZipFile(path) as archive:
            document_xml = archive.read("word/document.xml")
        root = ET.fromstring(document_xml)
    except (OSError, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise UploadError(field, f"Файл «{path.name}» повреждён или это не документ Word.") from exc

    text = " ".join(node.text or "" for node in root.iter(_WORD_TEXT)).strip()
    if not text:
        raise UploadError(field, f"Файл «{path.name}» не содержит текста.")
    try:
        parsed = parse_docx(path, "before")
    except Exception as exc:
        logger.warning(
            "Не удалось разобрать загруженный документ %s: %s", path.name, type(exc).__name__
        )
        raise UploadError(field, f"Файл «{path.name}» повреждён или это не документ Word.") from exc
    if not any(clause.number for clause in parsed.clauses):
        raise UploadError(
            field, f"В файле «{path.name}» нет нумерованных пунктов, разбор невозможен."
        )


async def with_timeout(run_id: str, coro, run_store=store) -> None:
    """Останавливает зависший анализ и сохраняет ошибку для опроса статуса."""
    try:
        await asyncio.wait_for(coro, timeout=PIPELINE_TIMEOUT_S)
    except TimeoutError:
        run_store.update_status(
            run_id,
            status="error",
            detail=(
                f"Анализ превысил {PIPELINE_TIMEOUT_S} с и остановлен; "
                "попробуйте меньше документов."
            ),
        )
    except Exception as exc:
        logger.error(
            "Фоновый анализ %s: %s: %s", run_id, type(exc).__name__, redact_secrets(str(exc))
        )
        run_store.update_status(
            run_id,
            status="error",
            detail="Анализ остановлен из-за внутренней ошибки. Попробуйте повторить запуск.",
        )
