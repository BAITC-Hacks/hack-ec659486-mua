"""Строгие ответы восьми LLM-вызовов и проверка ссылок на пункты.

Схемы вызовов соответствуют spec §5. Стабильный ``clause_id`` появляется в
``Source`` при сборке доменной модели: ответы LLM из §5 содержат печатные номера.
"""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, model_validator

from app.llm import strict_schema
from app.schemas import FunctionCategory, Modality, Severity, UnitChangeStatus

logger = logging.getLogger(__name__)


class StrictOut(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractedUnit(StrictOut):
    name: str
    parent: str
    clause_numbers: list[str]


class ExtractUnitsOut(StrictOut):
    units: list[ExtractedUnit]


class UnitPair(StrictOut):
    before: str
    after: str
    status: UnitChangeStatus
    note: str


class MatchUnitsOut(StrictOut):
    pairs: list[UnitPair]


class ExtractedFunction(StrictOut):
    text: str
    category: FunctionCategory
    executor: str | None
    modality: Modality
    clause_number: str
    context_clause_numbers: list[str]


class ExtractFunctionsOut(StrictOut):
    functions: list[ExtractedFunction]


class VerifyMatchesOut(StrictOut):
    decision: Literal["kept", "changed", "moved", "split", "merge", "partial", "none"]
    after_ids: list[str]
    rationale: str
    quotes: list[str]

    @model_validator(mode="after")
    def _none_has_no_candidates(self) -> VerifyMatchesOut:
        if self.decision == "none" and self.after_ids:
            raise ValueError("decision=none требует пустого after_ids")
        return self


class ConfirmLossOut(StrictOut):
    lost: bool
    nearest_clause_number: str | None
    nearest_quote: str
    rationale: str


class VerifyDuplicatesOut(StrictOut):
    is_duplicate: bool
    same_action: bool
    same_object: bool
    both_executors: bool
    verification_note: str

    @model_validator(mode="after")
    def _duplicate_requires_all_signs(self) -> VerifyDuplicatesOut:
        if self.is_duplicate and not (
            self.same_action and self.same_object and self.both_executors
        ):
            raise ValueError("дубль требует совпадения действия, объекта и двух исполнителей")
        return self


class ExplainConflictOut(StrictOut):
    explanation: str
    severity: Severity
    verified: bool
    verification_note: str


class WriteConclusionOut(StrictOut):
    conclusion_md: str
    recommendations: list[str]


EXTRACT_UNITS_SCHEMA = strict_schema(ExtractUnitsOut)
MATCH_UNITS_SCHEMA = strict_schema(MatchUnitsOut)
EXTRACT_FUNCTIONS_SCHEMA = strict_schema(ExtractFunctionsOut)
VERIFY_MATCHES_SCHEMA = strict_schema(VerifyMatchesOut)
CONFIRM_LOSS_SCHEMA = strict_schema(ConfirmLossOut)
VERIFY_DUPLICATES_SCHEMA = strict_schema(VerifyDuplicatesOut)
EXPLAIN_CONFLICT_SCHEMA = strict_schema(ExplainConflictOut)
WRITE_CONCLUSION_SCHEMA = strict_schema(WriteConclusionOut)

SCHEMAS: dict[str, tuple[type[BaseModel], dict[str, Any]]] = {
    "extract_units": (ExtractUnitsOut, EXTRACT_UNITS_SCHEMA),
    "match_units": (MatchUnitsOut, MATCH_UNITS_SCHEMA),
    "extract_functions": (ExtractFunctionsOut, EXTRACT_FUNCTIONS_SCHEMA),
    "verify_matches": (VerifyMatchesOut, VERIFY_MATCHES_SCHEMA),
    "confirm_loss": (ConfirmLossOut, CONFIRM_LOSS_SCHEMA),
    "verify_duplicates": (VerifyDuplicatesOut, VERIFY_DUPLICATES_SCHEMA),
    "explain_conflict": (ExplainConflictOut, EXPLAIN_CONFLICT_SCHEMA),
    "write_conclusion": (WriteConclusionOut, WRITE_CONCLUSION_SCHEMA),
}


def validate_clause_numbers(result: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    """Убирает чужие ссылки из ответа, не повышая статус проверки.

    ``allowed`` содержит печатные номера, а для ``after_ids`` — ID кандидатов,
    переданных в конкретный вызов. Возвращает независимую копию ответа.
    """
    cleaned = deepcopy(result)
    dropped = 0
    if isinstance(cleaned.get("units"), list):
        units = []
        for unit in cleaned["units"]:
            numbers = unit["clause_numbers"]
            unit["clause_numbers"] = [number for number in numbers if number in allowed]
            dropped += len(numbers) - len(unit["clause_numbers"])
            if unit["clause_numbers"]:
                units.append(unit)
        cleaned["units"] = units
    if isinstance(cleaned.get("functions"), list):
        functions = []
        for function in cleaned["functions"]:
            if function["clause_number"] not in allowed:
                dropped += 1
                continue
            numbers = function["context_clause_numbers"]
            function["context_clause_numbers"] = [number for number in numbers if number in allowed]
            dropped += len(numbers) - len(function["context_clause_numbers"])
            functions.append(function)
        cleaned["functions"] = functions
    if isinstance(cleaned.get("after_ids"), list):
        ids = cleaned["after_ids"]
        cleaned["after_ids"] = [identifier for identifier in ids if identifier in allowed]
        dropped += len(ids) - len(cleaned["after_ids"])
    if cleaned.get("nearest_clause_number") is not None:
        if cleaned["nearest_clause_number"] not in allowed:
            cleaned["nearest_clause_number"] = None
            dropped += 1
    logger.info("LLM: отброшено чужих ссылок на пункты/кандидатов: %d", dropped)
    return cleaned


def _field(value: Any, name: str) -> Any:
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def validate_sources(result: dict[str, Any], documents: list[Any]) -> dict[str, Any]:
    """Помечает находки с недостоверными ``Source`` как непроверенные.

    Применяется после сборки источников с ``doc_id`` и ``clause_id``. Не удаляет
    находку и не подменяет цитату. Для голых ответов spec §5 без ``sources``
    проверка не применима; вызывающий код сначала должен привязать Source.
    """
    cleaned = deepcopy(result)
    by_clause: dict[tuple[str, str], tuple[Any, Any]] = {}
    for document in documents:
        for clause in _field(document, "clauses") or []:
            by_clause[(_field(document, "id"), _field(clause, "id"))] = (document, clause)

    def check(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                check(item)
            return
        if not isinstance(node, dict):
            return
        sources = node.get("sources")
        if isinstance(sources, list):
            reasons: list[str] = []
            if not sources:
                reasons.append("нет источников")
            for source in sources:
                found = by_clause.get((_field(source, "doc_id"), _field(source, "clause_id")))
                if found is None:
                    reasons.append("адрес пункта не найден")
                    continue
                document, clause = found
                if (
                    _field(source, "doc_name") != _field(document, "name")
                    or _field(source, "version") != _field(document, "version")
                    or _field(source, "clause_number") != _field(clause, "number")
                ):
                    reasons.append("реквизиты источника не совпадают с пунктом")
                quote = _field(source, "quote")
                if not isinstance(quote, str) or not quote.strip() or (
                    _space(quote) not in _space(_field(clause, "text") or "")
                ):
                    reasons.append("цитата отсутствует в тексте пункта")
                executor = node.get("executor")
                if executor and _space(executor) not in _space(
                    f"{_field(clause, 'text') or ''} {_field(clause, 'lead_in') or ''}"
                ):
                    reasons.append("исполнитель не указан в пункте или его вводной")
            if reasons:
                node["verified"] = False
                reason = "; ".join(dict.fromkeys(reasons))
                prior = node.get("verification_note", "")
                node["verification_note"] = f"{prior}; {reason}" if prior else reason
                logger.info("Источник находки не прошёл проверку: %s", reason)
        for value in node.values():
            if isinstance(value, (dict, list)):
                check(value)

    check(cleaned)
    return cleaned
