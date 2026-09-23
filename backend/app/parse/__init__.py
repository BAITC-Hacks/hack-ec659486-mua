"""P1: разбор документов в пункты с контекстом (см. app.parse.docx)."""

from app.parse.docx import (
    DUTY_MARKERS,
    PROHIBITION_MARKERS,
    RIGHT_MARKERS,
    clause_modality,
    detect_modality,
    get_clause,
    lead_in_modality,
    parse_docx,
)

__all__ = [
    "DUTY_MARKERS",
    "PROHIBITION_MARKERS",
    "RIGHT_MARKERS",
    "clause_modality",
    "detect_modality",
    "get_clause",
    "lead_in_modality",
    "parse_docx",
]
