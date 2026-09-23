"""API запусков анализа (spec §4): загрузка комплекта, фоновый прогон, статус, отчёт, пункт, .md.

Прогон — фоновая задача `app.pipeline.start` (asyncio), статус опрашивается фронтом. Ошибки —
{error, detail} с русским текстом (форматирует app.main).
"""

import asyncio
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from app import pipeline, store
from app.config import BACKEND_DIR, get_settings
from app.schemas import Clause, Report, RunCreated, RunStatus, empty_stats
from app.validation import UploadError, validate_docx_content, with_timeout

router = APIRouter(prefix="/api/runs", tags=["runs"])

MAX_FILES_TOTAL = 10
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED_SUFFIX = ".docx"

DEMO_BEFORE = "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx"
DEMO_AFTER = "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx"

READY_STATES = ("done", "partial")
_UNSAFE_NAME = re.compile(r"[^\w.\- ]+")
_TASKS: set[asyncio.Task[None]] = set()


def api_error(status_code: int, error: str, detail: str) -> HTTPException:
    """HTTPException, тело которой app.main отдаёт как {error, detail} с русским текстом."""
    return HTTPException(status_code=status_code, detail={"error": error, "detail": detail})


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _data_dir() -> Path:
    """settings.data_dir; относительный путь — от каталога backend/, а не от cwd."""
    path = Path(get_settings().data_dir)
    return path if path.is_absolute() else BACKEND_DIR / path


def _create_run(run_id: str, inputs: dict[str, list[dict[str, str]]], detail: str) -> RunCreated:
    """Запись в очереди с пустым отчётом; прогон ставится фоновой задачей."""
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
    store.put(run_id, store.RunRecord(status=status, report=report, inputs=inputs))
    task = asyncio.create_task(
        with_timeout(run_id, pipeline.run_pipeline(run_id), store), name=f"run-{run_id}"
    )
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return RunCreated(run_id=run_id)


def _get_record(run_id: str) -> store.RunRecord:
    record = store.get(run_id)
    if record is None:
        raise api_error(404, "run_not_found", f"Запуск «{run_id}» не найден.")
    return record


def _safe_name(name: str) -> str:
    base = Path(name.replace("\\", "/")).name
    return (_UNSAFE_NAME.sub("_", base).strip(" .") or "document.docx")[-120:]


async def _read_upload(
    before: list[UploadFile], after: list[UploadFile]
) -> dict[str, list[tuple[str, bytes]]]:
    """Только .docx, ≤10 файлов суммарно на обе зоны, ≤10 МБ каждый, обе зоны непустые.

    Нарушение — 422 {error, detail}. Возвращает (имя, содержимое) по версиям.
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
    files: dict[str, list[tuple[str, bytes]]] = {"before": [], "after": []}
    for version, uploads in (("before", before), ("after", after)):
        for upload in uploads:
            name = upload.filename or ""
            if not name.lower().endswith(ALLOWED_SUFFIX):
                raise api_error(
                    422,
                    "unsupported_format",
                    f"Файл «{name or 'без имени'}»: формат не поддержан в прототипе, "
                    "загрузите документ Word в формате .docx.",
                )
            content = await upload.read()
            if len(content) > MAX_FILE_BYTES:
                raise api_error(
                    422,
                    "file_too_large",
                    f"Файл «{name}» больше {MAX_FILE_BYTES // (1024 * 1024)} МБ.",
                )
            files[version].append((name, content))
    return files


@router.post("", response_model=RunCreated, status_code=201)
async def create_run(
    before: Annotated[
        list[UploadFile], File(description="Документы до реорганизации (.docx)")
    ] = [],
    after: Annotated[
        list[UploadFile], File(description="Документы после реорганизации (.docx)")
    ] = [],
    before_list: Annotated[
        list[UploadFile], File(alias="before[]", description="То же, поле before[]")
    ] = [],
    after_list: Annotated[
        list[UploadFile], File(alias="after[]", description="То же, поле after[]")
    ] = [],
) -> RunCreated:
    """Принимает комплекты «до» и «после» (поля before/after или before[]/after[]), сохраняет
    файлы в {runtime_dir}/runs/{run_id}/ и запускает анализ в фоне."""
    files = await _read_upload([*before, *before_list], [*after, *after_list])
    run_id = uuid4().hex[:12]
    inputs: dict[str, list[dict[str, str]]] = {"before": [], "after": []}
    try:
        for version, items in files.items():
            folder = store.run_dir(run_id) / version
            folder.mkdir(parents=True, exist_ok=True)
            for number, (name, content) in enumerate(items, start=1):
                path = folder / f"{number:02d}_{_safe_name(name)}"
                path.write_bytes(content)
                validate_docx_content(path, version)
                display = Path(name.replace("\\", "/")).name or path.name
                inputs[version].append({"path": str(path), "name": display})
    except UploadError as exc:
        raise api_error(422, "validation", f"{exc.field}: {exc.reason}") from exc
    except OSError as exc:
        raise api_error(
            500, "storage_error", f"Не удалось сохранить загруженные файлы: {exc.strerror}."
        ) from exc
    total = sum(len(items) for items in files.values())
    return _create_run(run_id, inputs, f"Принято файлов: {total}. Анализ в очереди.")


@router.post("/demo", response_model=RunCreated, status_code=201)
async def create_demo_run() -> RunCreated:
    """Запуск на тестовом комплекте data/case11: редакция 8 — «до», редакция 9 — «после»."""
    data_dir = _data_dir() / "case11"
    missing = [name for name in (DEMO_BEFORE, DEMO_AFTER) if not (data_dir / name).is_file()]
    if missing:
        raise api_error(
            500,
            "demo_missing",
            "Тестовый комплект не найден: " + ", ".join(missing) + f" (каталог {data_dir}).",
        )
    try:
        validate_docx_content(data_dir / DEMO_BEFORE, "before")
        validate_docx_content(data_dir / DEMO_AFTER, "after")
    except UploadError as exc:
        raise api_error(422, "validation", f"{exc.field}: {exc.reason}") from exc
    inputs = {
        "before": [{"path": str(data_dir / DEMO_BEFORE), "name": DEMO_BEFORE}],
        "after": [{"path": str(data_dir / DEMO_AFTER), "name": DEMO_AFTER}],
    }
    return _create_run(
        uuid4().hex[:12], inputs, "Тестовый комплект: редакции 8 и 9. Анализ в очереди."
    )


@router.get("/{run_id}", response_model=RunStatus)
def get_run(run_id: str) -> RunStatus:
    return _get_record(run_id).status


@router.get("/{run_id}/report", response_model=Report)
def get_report(run_id: str) -> Report:
    """Отчёт — после done или partial (partial: часть шагов не выполнена, см. missing_steps)."""
    record = _get_record(run_id)
    status = record.status
    if status.status == "error":
        raise api_error(
            404, "run_failed", f"Анализ завершился ошибкой, отчёт не сформирован: {status.detail}"
        )
    if status.status not in READY_STATES:
        raise api_error(
            404,
            "report_not_ready",
            f"Отчёт ещё не готов: анализ выполняется ({status.progress}%).",
        )
    return record.report


@router.get(
    "/{run_id}/report.md",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/markdown": {}}, "description": "Заключение в Markdown"}},
)
def get_report_md(run_id: str) -> PlainTextResponse:
    """Заключение для скачивания: экспорт app.export_md или заголовок + conclusion_md."""
    record = _get_record(run_id)
    report = record.report
    if record.status.status in READY_STATES and record.markdown:
        body = record.markdown.rstrip() + "\n"
        if run_id not in body:
            body += f"\n---\nЗапуск ОргДифф {run_id}, {report.created_at}.\n"
    elif record.status.status in READY_STATES:
        body = f"# Заключение ОргДифф — запуск {run_id}\n\n{report.conclusion_md}".rstrip() + "\n"
    else:
        body = (
            f"# Заключение ОргДифф — запуск {run_id}\n\n"
            f"Отчёт ещё не готов: {record.status.detail or record.status.status}\n"
        )
    return PlainTextResponse(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="orgdiff-{run_id}.md"'},
    )


@router.get("/{run_id}/clauses/{doc_id}/{clause_number}", response_model=Clause)
def get_clause(run_id: str, doc_id: str, clause_number: str) -> Clause:
    """Пункт для панели источника: ищем по печатному номеру, затем по Clause.id."""
    report = _get_record(run_id).report
    for document in [*report.before_documents, *report.after_documents]:
        if document.id != doc_id:
            continue
        for clause in document.clauses:
            if clause.number == clause_number:
                return clause
        for clause in document.clauses:
            if clause.id == clause_number:
                return clause
        raise api_error(
            404,
            "clause_not_found",
            f"Пункт «{clause_number}» в документе «{document.name}» не найден.",
        )
    raise api_error(
        404, "document_not_found", f"Документ «{doc_id}» в запуске «{run_id}» не найден."
    )
