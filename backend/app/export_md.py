"""Читаемый Markdown-экспорт отчёта с адресами и цитатами источников."""

from __future__ import annotations

from collections.abc import Iterable

from app.schemas import Report, Source


def _cell(value: object) -> str:
    return str(value if value not in (None, "") else "—").replace("|", "\\|").replace("\n", "<br>")


def _table(columns: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "не найдено"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _points(sources: Iterable[Source]) -> str:
    seen: set[tuple[str, str, str | None]] = set()
    labels: list[str] = []
    for source in sources:
        key = source.doc_id, source.clause_id, source.clause_number
        if key in seen:
            continue
        seen.add(key)
        edition = "до" if source.version == "before" else "после"
        labels.append(f"{source.doc_name} ({edition}), п. {source.clause_number or 'без номера'}")
    return "; ".join(labels) or "—"


def _all_sources(report: Report) -> list[Source]:
    collected: list[Source] = []
    for change in report.unit_changes:
        collected.extend(change.sources)
    for match in report.function_matches:
        collected.extend(match.sources)
        for function in match.before + match.after:
            collected.extend(function.sources)
    for duplicate in report.duplicates:
        collected.extend(duplicate.function_a.sources)
        collected.extend(duplicate.function_b.sources)
    for conflict in report.conflicts:
        collected.extend(conflict.sources)
        for function in conflict.functions:
            collected.extend(function.sources)
    for constraint in report.constraints:
        collected.extend(constraint.sources)
    seen: set[tuple[str, str, str]] = set()
    unique: list[Source] = []
    for source in collected:
        key = source.doc_id, source.clause_id, source.quote
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def _names(report: Report, ids: list[str]) -> str:
    units = {
        unit.id: unit.name
        for change in report.unit_changes
        for unit in (change.unit_before, change.unit_after)
        if unit is not None
    }
    return "; ".join(units.get(unit_id, unit_id) for unit_id in ids) or "—"


def export_markdown(report: Report) -> str:
    """Экспортирует полный отчёт; непроверенные кандидаты помечает отдельно."""
    docs = report.before_documents + report.after_documents
    doc_names = (
        "; ".join(
            f"{doc.name} (редакция «{'до' if doc.version == 'before' else 'после'}»)"
            for doc in docs
        )
        or "не указаны"
    )
    sections = [
        "# Заключение по сравнению организационных документов",
        f"Документы: {doc_names}.",
        f"Дата отчёта: {report.created_at}.",
        "Ограничение: разобраны только .docx; PDF и Excel в прототипе не поддержаны.",
        "## Сводка",
        _table(
            ["Показатель", "Значение"],
            [[key, value] for key, value in report.stats.items()],
        ),
        "## Подразделения",
        _table(
            ["Статус", "До", "После", "Пункты"],
            [
                [
                    change.status,
                    change.unit_before.name if change.unit_before else "—",
                    change.unit_after.name if change.unit_after else "—",
                    _points(change.sources),
                ]
                for change in report.unit_changes
            ],
        ),
        "## Функции",
        _table(
            ["Статус", "Вид связи", "До", "После", "Пункты до", "Пункты после"],
            [
                [
                    match.status,
                    match.kind,
                    "; ".join(function.text for function in match.before) or "—",
                    "; ".join(function.text for function in match.after) or "—",
                    _points(source for source in match.sources if source.version == "before"),
                    _points(source for source in match.sources if source.version == "after"),
                ]
                for match in report.function_matches
                if match.verified
            ],
        ),
        "## Кандидаты в потери — требует проверки",
        _table(
            ["Функция до", "Причина проверки", "Пункты"],
            [
                [
                    "; ".join(function.text for function in match.before),
                    match.note or "Требует проверки по редакции «после»",
                    _points(match.sources),
                ]
                for match in report.function_matches
                if match.status == "lost" and not match.verified
            ],
        ),
        "## Ограничения",
        _table(
            ["Запрет", "Исполнитель", "Пункты"],
            [
                [item.text, item.executor or "—", _points(item.sources)]
                for item in report.constraints
            ],
        ),
        "## Дубли",
        _table(
            ["Статус", "Функция A", "Функция B", "Объяснение", "Пункты"],
            [
                [
                    "подтверждено" if item.verified else "требует проверки",
                    item.function_a.text,
                    item.function_b.text,
                    item.note if item.verified else item.verification_note or item.note,
                    _points(item.function_a.sources + item.function_b.sources),
                ]
                for item in report.duplicates
            ],
        ),
        "## Конфликты интересов",
        _table(
            ["Статус", "Правило", "Шаблон ролей", "Подразделения", "Объяснение", "Пункты"],
            [
                [
                    "подтверждено" if item.verified else "требует проверки",
                    item.rule_id,
                    item.role_pattern,
                    _names(report, item.units),
                    (
                        item.explanation
                        if item.verified
                        else item.verification_note or item.explanation
                    ),
                    _points(item.sources),
                ]
                for item in report.conflicts
            ],
        ),
        "## Заключение",
        report.conclusion_md.strip() or "не найдено",
        "## Рекомендации",
        "\n".join(f"- {item}" for item in report.recommendations)
        if report.recommendations
        else "рекомендации не сформированы",
        "## Источники",
    ]
    sources = _all_sources(report)
    if sources:
        sections.extend(
            f"- {source.doc_name}, редакция «{'до' if source.version == 'before' else 'после'}», "
            f"п. {source.clause_number or 'без номера'}: «{source.quote}»"
            for source in sources
        )
    else:
        sections.append("не найдено")
    return "\n\n".join(sections).rstrip() + "\n"
