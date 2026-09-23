"""P6: проверенные факты, интерпретация LLM и заключение с источниками."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from app.llm import LLM, MOCKS_DIR, LLMError, validate_output
from app.llm_schemas import WRITE_CONCLUSION_SCHEMA, WriteConclusionOut
from app.schemas import Report, Source

logger = logging.getLogger(__name__)
PROMPT = Path(__file__).resolve().parent / "prompts" / "write_conclusion.md"
FINDING_REF = re.compile(r"\[F(\d+)\]")


def _sources(sources: list[Source], report: Report) -> list[dict[str, Any]]:
    """Оставляет только цитаты с действительным адресом пункта в загруженном документе."""
    clauses = {
        (doc.id, clause.id): (doc, clause)
        for doc in report.before_documents + report.after_documents
        for clause in doc.clauses
    }
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        found = clauses.get((source.doc_id, source.clause_id))
        if found is None:
            logger.info("Заключение: источник %s/%s не найден", source.doc_id, source.clause_id)
            continue
        doc, clause = found
        if (
            source.doc_name != doc.name
            or source.version != doc.version
            or source.clause_number != clause.number
            or not source.quote.strip()
            or " ".join(source.quote.split()).casefold()
            not in " ".join(clause.text.split()).casefold()
        ):
            logger.info("Заключение: реквизиты или цитата пункта %s не совпали", source.clause_id)
            continue
        key = (source.doc_id, source.clause_id, source.quote)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "doc": source.doc_name,
                "version": source.version,
                "clause_number": source.clause_number,
                "quote": source.quote,
            }
        )
    return result


def build_facts(report: Report) -> dict[str, Any]:
    """Готовит только прослеживаемые находки для P6, с общей нумерацией F1…"""
    verified: list[dict[str, Any]] = []
    unverified: list[dict[str, Any]] = []
    number = 0

    def add(
        *,
        category: str,
        kind: str,
        status: str,
        summary: str,
        confirmed: bool,
        verification: str,
        sources: list[Source],
        reason: str = "",
    ) -> None:
        nonlocal number
        checked = _sources(sources, report)
        if not checked:
            logger.info("Заключение: находка %s без подтверждённого источника пропущена", category)
            return
        number += 1
        fact = {
            "id": f"F{number}",
            "category": category,
            "kind": kind,
            "status": status,
            "summary": summary.strip(),
            "verified": confirmed,
            "verification": verification,
            "verification_note": reason.strip(),
            "sources": checked,
        }
        (verified if confirmed else unverified).append(fact)

    for change in report.unit_changes:
        before = change.unit_before.name if change.unit_before else "—"
        after = change.unit_after.name if change.unit_after else "—"
        add(
            category="unit_change",
            kind="unit_change",
            status=change.status,
            summary=f"{before} → {after}. {change.note}",
            confirmed=True,
            verification="document",
            sources=change.sources,
        )
    for match in report.function_matches:
        if match.status == "kept":
            continue
        before = "; ".join(function.text for function in match.before) or "—"
        after = "; ".join(function.text for function in match.after) or "—"
        add(
            category="function_match",
            kind=match.kind,
            status=match.status,
            summary=f"До: {before}. После: {after}. {match.note}",
            confirmed=match.verified,
            verification=match.verification,
            sources=match.sources,
            reason=match.note if not match.verified else "",
        )
    for duplicate in report.duplicates:
        add(
            category="duplicate",
            kind="duplicate",
            status="duplicate",
            summary=(
                f"{duplicate.function_a.text} / {duplicate.function_b.text}. {duplicate.note}"
            ),
            confirmed=duplicate.verified,
            verification="llm" if duplicate.verified else "pending",
            sources=duplicate.function_a.sources + duplicate.function_b.sources,
            reason=duplicate.verification_note,
        )
    for conflict in report.conflicts:
        add(
            category="conflict",
            kind=conflict.rule_id,
            status="conflict",
            summary=f"{conflict.title}: {conflict.explanation}",
            confirmed=conflict.verified,
            verification="llm" if conflict.verified else "pending",
            sources=conflict.sources,
            reason=conflict.verification_note,
        )

    constraints = [
        {"text": item.text, "sources": checked}
        for item in report.constraints
        if (checked := _sources(item.sources, report))
    ]
    return {
        "findings": verified,
        "unverified": unverified,
        "constraints": constraints,
        "stats": {**report.stats, "unverified_candidates": len(unverified)},
        "documents": [
            {"name": doc.name, "version": doc.version}
            for doc in report.before_documents + report.after_documents
        ],
        "limitations": ["Разобраны только .docx; PDF и Excel в прототипе не поддержаны."],
    }


def _fixture_path(report_facts: dict[str, Any]) -> Path:
    raw = json.dumps(report_facts, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return MOCKS_DIR / "write_conclusion" / f"{digest}.json"


def _call_llm(report_facts: dict[str, Any], llm: LLM) -> WriteConclusionOut:
    path = _fixture_path(report_facts)
    if llm.mode == "mock":
        if not path.is_file():
            raise LLMError(
                f"нет mock-фикстуры для 'write_conclusion': ожидался файл "
                f"mocks/write_conclusion/{path.name}. Для своих документов нужен ключ "
                "OpenAI в .env (LLM_MODE=live)."
            )
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise LLMError(f"mock-фикстура {path} содержит невалидный JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise LLMError(f"mock-фикстура {path} должна содержать JSON-объект")
    else:
        data = llm.complete_json(
            "write_conclusion",
            system=PROMPT.read_text(encoding="utf-8"),
            user=json.dumps(report_facts, ensure_ascii=False),
            schema=WRITE_CONCLUSION_SCHEMA,
        )
        if os.environ.get("LLM_RECORD_MOCKS") == "1":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return validate_output(WriteConclusionOut, data, "write_conclusion")


def _source_label(source: dict[str, Any]) -> str:
    edition = "до" if source["version"] == "before" else "после"
    number = source["clause_number"] or "без номера"
    return f"{source['doc']} (редакция «{edition}»), п. {number}: «{source['quote']}»"


def write_conclusion(report_facts: dict[str, Any], llm: LLM) -> WriteConclusionOut:
    """Шаблонные факты плюс проверенная по ссылкам интерпретация модели."""
    findings = report_facts.get("findings", [])
    unverified = report_facts.get("unverified", [])
    if not findings and not unverified:
        return WriteConclusionOut(
            conclusion_md="Существенных изменений по документам не найдено.\n\n"
            "Ограничение: разобраны только .docx; PDF и Excel в прототипе не поддержаны.",
            recommendations=[],
        )

    result = _call_llm(report_facts, llm)
    known = {fact["id"] for fact in findings + unverified}
    unverified_ids = {fact["id"] for fact in unverified}
    model_paragraphs: list[str] = []
    for paragraph in re.split(r"\n\s*\n", result.conclusion_md.strip()):
        refs = {f"F{number}" for number in FINDING_REF.findall(paragraph)}
        if (
            not refs
            or not refs <= known
            or (refs & unverified_ids and "требует проверки" not in paragraph.lower())
        ):
            logger.info(
                "Заключение: абзац модели без допустимых ссылок отброшен: %s", paragraph[:120]
            )
            continue
        model_paragraphs.append(paragraph.strip())
    if not model_paragraphs:
        raise LLMError("LLM не вернула абзацев заключения с допустимыми ссылками на находки")

    parts: list[str] = ["### Подтверждённые находки"]
    for fact in findings:
        sources = "; ".join(_source_label(source) for source in fact["sources"])
        parts.append(f"[{fact['id']}] {fact['summary']} Источники: {sources}")
    if unverified:
        parts.append("### Требует проверки")
        for fact in unverified:
            sources = "; ".join(_source_label(source) for source in fact["sources"])
            reason = fact.get("verification_note") or "подтверждение не получено"
            parts.append(
                f"[{fact['id']}] Требует проверки: {fact['summary']} "
                f"Причина: {reason}. Источники: {sources}"
            )
    parts.append("### Интерпретация")
    parts.extend(model_paragraphs)
    parts.append("Ограничение: разобраны только .docx; PDF и Excel в прототипе не поддержаны.")

    recommendations: list[str] = []
    for recommendation in result.recommendations:
        refs = {f"F{number}" for number in FINDING_REF.findall(recommendation)}
        if refs and refs <= {fact["id"] for fact in findings}:
            recommendations.append(recommendation.strip())
        else:
            logger.info("Заключение: рекомендация без подтверждённой находки отброшена")
    return WriteConclusionOut(conclusion_md="\n\n".join(parts), recommendations=recommendations)
