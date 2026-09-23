"""Хранилище запусков: словарь в памяти + JSON-дамп каждой записи в runtime-каталог.

Дамп — для отладки и разбора прогона после демо (`{runtime_dir}/runs/{run_id}.json`), при старте
приложения не читается: `get` неизвестного id → None. Ошибка записи дампа не роняет прогон.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR, get_settings
from app.schemas import Report, RunStatus

logger = logging.getLogger(__name__)


@dataclass
class RunRecord:
    """Состояние одного запуска.

    status — для опроса фронтом; report — пустой, пока анализ не завершён; inputs — пути к
    документам по версиям; skipped — невыполненные шаги с причинами; markdown — экспорт .md.
    """

    status: RunStatus
    report: Report
    inputs: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    skipped: list[dict[str, str]] = field(default_factory=list)
    markdown: str | None = None


_RUNS: dict[str, RunRecord] = {}


def runtime_dir() -> Path:
    """settings.runtime_dir; относительный путь — от каталога backend/, а не от cwd."""
    path = Path(get_settings().runtime_dir)
    return path if path.is_absolute() else BACKEND_DIR / path


def run_dir(run_id: str) -> Path:
    """Каталог загруженных файлов запуска: {runtime_dir}/runs/{run_id}/."""
    return runtime_dir() / "runs" / run_id


def get(run_id: str) -> RunRecord | None:
    return _RUNS.get(run_id)


def put(run_id: str, record: RunRecord) -> None:
    _RUNS[run_id] = record
    _dump(run_id, record)


def update_status(run_id: str, **changes: Any) -> RunStatus | None:
    """Меняет поля RunStatus (status, progress, detail, missing_steps) с валидацией по схеме."""
    record = _RUNS.get(run_id)
    if record is None:
        return None
    record.status = RunStatus.model_validate({**record.status.model_dump(), **changes})
    _dump(run_id, record)
    return record.status


def set_result(
    run_id: str, report: Report, skipped: list[dict[str, str]], markdown: str | None
) -> None:
    """Сохраняет итог прогона (до смены статуса на done/partial, чтобы отчёт уже был на месте)."""
    record = _RUNS.get(run_id)
    if record is None:
        return
    record.report = report
    record.skipped = list(skipped)
    record.markdown = markdown
    _dump(run_id, record)


def _dump(run_id: str, record: RunRecord) -> None:
    path = runtime_dir() / "runs" / f"{run_id}.json"
    payload = {
        "status": record.status.model_dump(mode="json"),
        "inputs": record.inputs,
        "skipped": record.skipped,
        "report": record.report.model_dump(mode="json"),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
    except OSError as exc:
        logger.warning("Не удалось записать дамп запуска %s: %s", run_id, exc)
