"""Хранилище запусков: словарь в памяти + get/put. Логики пайплайна здесь нет.

S01: заглушка для контракта; в волне 2 переписывает S08 (JSON-дамп в runtime, фоновая задача).
"""

from dataclasses import dataclass

from app.schemas import Report, RunStatus


@dataclass
class RunRecord:
    """Состояние одного запуска: статус для опроса и отчёт (пустой, пока анализ не завершён)."""

    status: RunStatus
    report: Report


_RUNS: dict[str, RunRecord] = {}


def get(run_id: str) -> RunRecord | None:
    return _RUNS.get(run_id)


def put(run_id: str, record: RunRecord) -> None:
    _RUNS[run_id] = record
