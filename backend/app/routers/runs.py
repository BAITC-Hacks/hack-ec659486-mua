"""API запусков анализа (spec §4). S01: заглушки, отдающие валидные по контракту объекты.

В волне 2 S08 заменяет заглушки пайплайном (фоновая задача, JSON-дамп), сохраняя пути,
коды ответов и формат ошибок {error, detail}. Разбора docx и LLM здесь нет.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from app import store
from app.config import get_settings
from app.schemas import Clause, Report, RunCreated, RunStatus, empty_stats

router = APIRouter(prefix="/api/runs", tags=["runs"])

MAX_FILES_TOTAL = 10
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIX = ".docx"

DEMO_BEFORE = "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx"
DEMO_AFTER = "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx"


def api_error(status_code: int, error: str, detail: str) -> HTTPException:
    """HTTPException, тело которой app.main отдаёт как {error, detail} с русским текстом."""
    return HTTPException(status_code=status_code, detail={"error": error, "detail": detail})


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _new_run(detail: str | None) -> RunCreated:
    run_id = uuid4().hex[:12]
    status = RunStatus(run_id=run_id, status="queued", progress=0, detail=detail, missing_steps=[])
    report = Report(
        run_id=run_id,
        created_at=_now_iso(),
        before_documents=[],
        after_documents=[],
        unit_changes=[],
        function_matches=[],
        duplicates=[],
        conflicts=[],
        constraints=[],
        conclusion_md="",
        recommendations=[],
        stats=empty_stats(),
    )
    store.put(run_id, store.RunRecord(status=status, report=report))
    return RunCreated(run_id=run_id)


def _get_record(run_id: str) -> store.RunRecord:
    record = store.get(run_id)
    if record is None:
        raise api_error(404, "run_not_found", f"Запуск «{run_id}» не найден.")
    return record


async def _validate_upload(before: list[UploadFile], after: list[UploadFile]) -> None:
    """Только .docx, ≤10 файлов суммарно на обе зоны, ≤10 МБ каждый, обе зоны непустые.

    Нарушение — 422 {error, detail}.
    """
    if not before or not after:
        raise api_error(
            422,
            "missing_documents",
            "Загрузите хотя бы один документ «до» и один документ «после» реорганизации.",
        )
    if len(before) + len(after) > MAX_FILES_TOTAL:
        raise api_error(
            422,
            "too_many_files",
            f"Не более {MAX_FILES_TOTAL} файлов суммарно в зонах «до» и «после».",
        )
    for upload in [*before, *after]:
        name = upload.filename or ""
        if not name.lower().endswith(ALLOWED_SUFFIX):
            raise api_error(
                422,
                "unsupported_format",
                f"Файл «{name or 'без имени'}»: в прототипе поддерживается только формат .docx.",
            )
        content = await upload.read()
        await upload.seek(0)
        if len(content) > MAX_FILE_BYTES:
            raise api_error(
                422,
                "file_too_large",
                f"Файл «{name}» больше {MAX_FILE_BYTES // (1024 * 1024)} МБ.",
            )


@router.post("", response_model=RunCreated, status_code=201)
async def create_run(
    before: Annotated[
        list[UploadFile], File(description="Документы до реорганизации (.docx)")
    ] = [],
    after: Annotated[
        list[UploadFile], File(description="Документы после реорганизации (.docx)")
    ] = [],
) -> RunCreated:
    """Принимает комплекты «до» и «после», ставит анализ в очередь. Заглушка S01: без разбора."""
    await _validate_upload(before, after)
    names = [f.filename or "" for f in before] + [f.filename or "" for f in after]
    return _new_run(detail=f"Принято файлов: {len(names)}. Анализ ещё не запущен (заглушка S01).")


@router.post("/demo", response_model=RunCreated, status_code=201)
def create_demo_run() -> RunCreated:
    """Запуск на тестовом комплекте data/case11 (редакции 8 и 9). Заглушка S01: только очередь."""
    data_dir = Path(get_settings().data_dir) / "case11"
    missing = [name for name in (DEMO_BEFORE, DEMO_AFTER) if not (data_dir / name).is_file()]
    if missing:
        raise api_error(
            500,
            "demo_missing",
            "Тестовый комплект не найден: " + ", ".join(missing) + f" (каталог {data_dir}).",
        )
    return _new_run(detail="Тестовый комплект принят. Анализ ещё не запущен (заглушка S01).")


@router.get("/{run_id}", response_model=RunStatus)
def get_run(run_id: str) -> RunStatus:
    return _get_record(run_id).status


@router.get("/{run_id}/report", response_model=Report)
def get_report(run_id: str) -> Report:
    return _get_record(run_id).report


@router.get(
    "/{run_id}/report.md",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/markdown": {}}, "description": "Заключение в Markdown"}},
)
def get_report_md(run_id: str) -> PlainTextResponse:
    """Заключение для скачивания. Заглушка S01: заголовок и conclusion_md (полный экспорт — S14)."""
    report = _get_record(run_id).report
    body = (
        f"# Заключение ОргДифф — запуск {report.run_id}\n\n{report.conclusion_md}".rstrip() + "\n"
    )
    return PlainTextResponse(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="orgdiff-{report.run_id}.md"'},
    )


@router.get("/{run_id}/clauses/{doc_id}/{clause_number}", response_model=Clause)
def get_clause(run_id: str, doc_id: str, clause_number: str) -> Clause:
    """Пункт для панели источника: ищем по печатному номеру, затем по Clause.id."""
    report = _get_record(run_id).report
    for document in [*report.before_documents, *report.after_documents]:
        if document.id != doc_id:
            continue
        for clause in document.clauses:
            if clause.number == clause_number or clause.id == clause_number:
                return clause
        raise api_error(
            404,
            "clause_not_found",
            f"Пункт «{clause_number}» в документе «{document.name}» не найден.",
        )
    raise api_error(
        404, "document_not_found", f"Документ «{doc_id}» в запуске «{run_id}» не найден."
    )
