"""Контракт ответов LLM и отсечение выдуманных ссылок без сети."""

from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.llm_schemas import (
    SCHEMAS,
    VerifyDuplicatesOut,
    VerifyMatchesOut,
    validate_clause_numbers,
    validate_sources,
)
from app.schemas import Clause, Document

# Реальные номера из раздела 3 тестового комплекта редакций 8/9.
EXAMPLES = {
    "extract_units": {
        "units": [{"name": "Блок внутреннего аудита", "parent": "", "clause_numbers": ["3.4"]}]
    },
    "match_units": {
        "pairs": [
            {
                "before": "Блок внутреннего аудита",
                "after": "Блок внутреннего аудита",
                "status": "kept",
                "note": "Наименование сохранено.",
            }
        ]
    },
    "extract_functions": {
        "functions": [
            {
                "text": "Проводит внутренний аудит",
                "category": "function",
                "executor": "Блок внутреннего аудита",
                "modality": "duty",
                "clause_number": "3.4",
                "context_clause_numbers": ["3.2"],
            }
        ]
    },
    "verify_matches": {
        "decision": "kept",
        "after_ids": ["after-3.4"],
        "rationale": "Функция сохранена.",
        "quotes": ["3.4. Блок внутреннего аудита"],
    },
    "confirm_loss": {
        "lost": True,
        "nearest_clause_number": "3.2",
        "nearest_quote": "3.2. Структура блока",
        "rationale": "Совпадающей функции нет.",
    },
    "verify_duplicates": {
        "is_duplicate": True,
        "same_action": True,
        "same_object": True,
        "both_executors": True,
        "verification_note": "Оба исполнителя проводят аудит одного объекта.",
    },
    "explain_conflict": {
        "explanation": "Один исполнитель выполняет и проверяет действие.",
        "severity": "medium",
        "verified": True,
        "verification_note": "Подтверждено пунктами 3.2 и 3.4.",
    },
    "write_conclusion": {
        "conclusion_md": "По пунктам 3.2 и 3.4 требуется проверить распределение функций.",
        "recommendations": ["Проверить распределение функций."],
    },
}


def _assert_strict_objects(node: object) -> None:
    if isinstance(node, dict):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert node["required"] == list(node["properties"])
        for value in node.values():
            _assert_strict_objects(value)
    elif isinstance(node, list):
        for value in node:
            _assert_strict_objects(value)


@pytest.mark.parametrize("name", list(SCHEMAS))
def test_strict_schema_and_response(name: str) -> None:
    model, schema = SCHEMAS[name]
    assert schema["type"] == "object"
    _assert_strict_objects(schema)
    model.model_validate(EXAMPLES[name])
    with pytest.raises(ValidationError):
        model.model_validate({**EXAMPLES[name], "unexpected": 1})


@pytest.mark.parametrize(
    "name", ["extract_units", "extract_functions", "verify_matches", "confirm_loss"]
)
def test_validate_clause_numbers(name: str, caplog: pytest.LogCaptureFixture) -> None:
    value = deepcopy(EXAMPLES[name])
    allowed = {"3.2", "3.4", "after-3.4"}
    if name == "extract_units":
        value["units"][0]["clause_numbers"].append("99.9")
        value["units"].append({"name": "Фантом", "parent": "", "clause_numbers": ["98.8"]})
        expected_drops = 2
    elif name == "extract_functions":
        value["functions"][0]["context_clause_numbers"].append("99.9")
        value["functions"].append(
            {**value["functions"][0], "clause_number": "98.8", "text": "Выдуманная функция"}
        )
        expected_drops = 2
    elif name == "verify_matches":
        value["after_ids"].append("phantom")
        expected_drops = 1
    else:
        value["nearest_clause_number"] = "99.9"
        expected_drops = 1

    with caplog.at_level("INFO"):
        cleaned = validate_clause_numbers(value, allowed)
    assert cleaned == (
        {**EXAMPLES[name], "nearest_clause_number": None}
        if name == "confirm_loss"
        else EXAMPLES[name]
    )
    assert value != cleaned
    assert f": {expected_drops}" in caplog.text


def test_verify_duplicates_requires_all_signs() -> None:
    with pytest.raises(ValidationError):
        VerifyDuplicatesOut.model_validate({**EXAMPLES["verify_duplicates"], "same_object": False})


@pytest.mark.parametrize(
    "decision", ["kept", "changed", "moved", "split", "merge", "partial", "none"]
)
def test_all_match_decisions(decision: str) -> None:
    value = {**EXAMPLES["verify_matches"], "decision": decision}
    if decision == "none":
        value["after_ids"] = []
    VerifyMatchesOut.model_validate(value)


def test_validate_sources_marks_invalid_finding_without_deleting_it() -> None:
    clause = Clause(
        id="d9:p12:0",
        number="3.4",
        section="3. Структура",
        section_path=["3. Структура"],
        text="3.4. Блок внутреннего аудита проводит проверки.",
        index=12,
        lead_in="Блок внутреннего аудита:",
        modality="duty",
    )
    document = Document(
        id="d9", name="редакция-9.docx", version="after", kind="polozhenie", clauses=[clause]
    )
    source = {
        "doc_id": "d9",
        "doc_name": "редакция-9.docx",
        "version": "after",
        "clause_id": "d9:p12:0",
        "clause_number": "3.4",
        "quote": "Блок  внутреннего\n аудита проводит проверки.",
    }
    result = {"functions": [{"executor": "Блок внутреннего аудита", "sources": [source]}]}
    assert validate_sources(result, [document]) == result
    bad = deepcopy(result)
    bad["functions"][0]["sources"][0]["quote"] = "неизвестная цитата"
    checked = validate_sources(bad, [document])
    assert checked["functions"][0]["verified"] is False
    assert "цитата" in checked["functions"][0]["verification_note"]
    assert "verified" not in bad["functions"][0]


def test_validate_sources_rejects_wrong_executor_and_address() -> None:
    result = {
        "functions": [
            {
                "executor": "Несуществующий отдел",
                "sources": [
                    {
                        "doc_id": "d9",
                        "doc_name": "редакция-9.docx",
                        "version": "after",
                        "clause_id": "missing",
                        "clause_number": "3.4",
                        "quote": "цитата",
                    }
                ],
            }
        ]
    }
    checked = validate_sources(result, [])
    assert checked["functions"][0]["verified"] is False
    assert "адрес" in checked["functions"][0]["verification_note"]
