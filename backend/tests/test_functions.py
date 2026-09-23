"""P3 «Функции и запреты» (S09): выбор пунктов, наследование исполнителя, запреты, фикстуры.

Документы тестового комплекта разбираются настоящим парсером S04 (`app.parse.docx`),
подразделения — S05 (`detect_units` на его mock-фикстурах). Проверки на фикстурах комплекта
не опираются на конкретные формулировки: они должны остаться зелёными, когда S15 заменит
черновые фикстуры реальными ответами модели. Проверки кода (чужие номера, запрет по вводной,
исполнитель из вводной, кэш) идут на подставном LLM в live-режиме.
"""

import logging
import random
from pathlib import Path
from typing import Any

import pytest

from app.config import Settings
from app.functions import (
    ExtractFunctionsOut,
    assign_clauses,
    build_payload,
    clear_cache,
    executor_phrase,
    extract_all,
    extract_functions,
    function_clauses,
    mock_fixture_path,
)
from app.llm import LLM, LLMError, strict_schema
from app.parse.docx import get_clause, lead_in_modality, parse_docx
from app.schemas import Clause, Document, Function, Unit
from app.units import detect_units

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "case11"
DOC_BEFORE = "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx"
DOC_AFTER = "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx"
REQUIRED = ("2.4.2", "2.4.9", "2.4.10", "5.1.1", "5.1.4")


def mock_llm() -> LLM:
    return LLM(Settings(llm_mode="mock", openai_api_key=None))


class FakeLLM(LLM):
    """Live-режим без сети: complete_json отдаёт заданный ответ и считает вызовы."""

    def __init__(self, answer: dict[str, Any]) -> None:
        super().__init__(Settings(llm_mode="live", openai_api_key="test-key-not-used"))
        self.answer = answer
        self.calls = 0

    def complete_json(
        self, name: str, system: str, user: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls += 1
        assert name == "extract_functions"
        assert "атомарные функции" in system
        return self.answer


@pytest.fixture(autouse=True)
def _fresh_cache() -> None:
    clear_cache()


@pytest.fixture(scope="module")
def kit() -> dict[str, Any]:
    before = parse_docx(DATA_DIR / DOC_BEFORE, "before")
    after = parse_docx(DATA_DIR / DOC_AFTER, "after")
    units = detect_units(before, after, mock_llm())
    return {
        "before": before,
        "after": after,
        "units_before": units.units_before,
        "units_after": units.units_after,
    }


@pytest.fixture(scope="module")
def extracted(kit: dict[str, Any]) -> dict[str, tuple[list[Function], list[Function]]]:
    return {
        version: extract_all(kit[version], kit[f"units_{version}"], mock_llm())
        for version in ("before", "after")
    }


def _clause(doc: Document, number: str) -> Clause:
    clause = get_clause(doc, number)
    assert clause is not None, number
    return clause


def _item(clause_number: str, **overrides: Any) -> dict[str, Any]:
    item = {
        "text": "текст функции",
        "category": "duty",
        "executor": None,
        "modality": "duty",
        "clause_number": clause_number,
        "context_clause_numbers": [],
    }
    item.update(overrides)
    return item


# --- Тестовый комплект на mock-фикстурах -----------------------------------------------------


@pytest.mark.parametrize("version", ["before", "after"])
def test_kit_functions_have_verified_sources(
    kit: dict[str, Any], extracted: dict[str, Any], version: str
) -> None:
    doc: Document = kit[version]
    functions, constraints = extracted[version]
    assert len(functions) >= 15
    by_number = {c.number: c for c in doc.clauses if c.number}
    unit_ids = {u.id for u in kit[f"units_{version}"]}
    for fn in functions + constraints:
        assert fn.sources and fn.signature and fn.text.strip()
        assert fn.unit_id in unit_ids
        for src in fn.sources:
            assert src.doc_id == doc.id and src.version == version
            clause = by_number.get(src.clause_number)
            assert clause is not None, f"пункта {src.clause_number} нет в документе"
            assert src.quote == clause.text
            assert src.clause_id == clause.id
        assert all(n in by_number for n in fn.context_clause_numbers)
        assert fn.sources[0].clause_number not in fn.context_clause_numbers
    assert len({fn.id for fn in functions + constraints}) == len(functions) + len(constraints)
    numbers = {fn.sources[0].clause_number for fn in functions}
    assert set(REQUIRED) <= numbers


@pytest.mark.parametrize("version", ["before", "after"])
def test_prohibitions_are_constraints_not_functions(
    kit: dict[str, Any], extracted: dict[str, Any], version: str
) -> None:
    doc: Document = kit[version]
    functions, constraints = extracted[version]
    prohibited = {
        c.number for c in doc.clauses if c.number and lead_in_modality(c.lead_in) == "prohibition"
    }
    assert prohibited, "в комплекте есть перечень под «не имеют права:»"
    assert all(fn.modality != "prohibition" for fn in functions)
    assert not {fn.sources[0].clause_number for fn in functions} & prohibited
    assert constraints and all(fn.modality == "prohibition" for fn in constraints)
    assert {fn.sources[0].clause_number for fn in constraints} & prohibited


@pytest.mark.parametrize(
    ("version", "number", "executor"),
    [
        ("before", "5.1.4", "Главный аудитор"),
        ("after", "5.1.4", "Главный аудитор"),
        ("after", "5.3.7", "Директоры департаментов и Директоры направлений ДИТААД и ДОА"),
        ("before", "5.4.2", "Директор департамента непрерывного мониторинга"),
    ],
)
def test_executor_inherited_from_lead_in(
    extracted: dict[str, Any], version: str, number: str, executor: str
) -> None:
    functions, _ = extracted[version]
    matched = [fn for fn in functions if fn.sources[0].clause_number == number]
    assert matched
    assert all(fn.executor and fn.executor.startswith(executor) for fn in matched)


def test_clauses_assigned_to_one_owner(kit: dict[str, Any]) -> None:
    for version in ("before", "after"):
        doc, units = kit[version], kit[f"units_{version}"]
        groups = assign_clauses(doc, units)
        ids = [c.id for clauses in groups.values() for c in clauses]
        assert len(ids) == len(set(ids)) == len(function_clauses(doc))
    names = {u.id: u.name for u in kit["units_before"] + kit["units_after"]}

    def owner(version: str, number: str) -> str:
        groups = assign_clauses(kit[version], kit[f"units_{version}"])
        clause = _clause(kit[version], number)
        return next(names[uid] for uid, cl in groups.items() if uid and clause in cl)

    assert "ДНМ" in owner("before", "5.4.4.а")  # вводная «Директор департамента … мониторинга»
    assert "ДНМ" in owner("before", "5.7.1")  # вводная «Директор ДНМ обязан …, имеет право:»
    assert "ДККМ" in owner("before", "5.5.11")  # «формирует план работ БВА» — но под ДККМ
    assert owner("before", "5.3.4.а") == "Направление внутреннего аудита"
    assert "ДИТААД" in owner("after", "5.3.2.а")  # вводная называет двоих, пункт — одного
    assert "БВА" in owner("after", "5.3.1")  # вводная на двоих → общий родитель
    assert "БВА" in owner("after", "4.4.а")  # «…, БВА:»


def test_function_scope_skips_headings_and_unnumbered(kit: dict[str, Any]) -> None:
    doc: Document = kit["before"]
    scope = function_clauses(doc)
    assert scope and all(c.number for c in scope)
    assert {c.number for c in scope} >= set(REQUIRED)
    assert not any(c.number in ("2", "5") for c in scope)  # заголовки разделов
    sections = {c.section for c in scope}
    assert all(s and s.split(".")[0] in {"2", "4", "5"} for s in sections)


def test_whole_document_without_units(kit: dict[str, Any]) -> None:
    functions, constraints = extract_all(kit["after"], [], mock_llm())
    assert len(functions) >= 15 and constraints
    assert all(fn.unit_id is None for fn in functions + constraints)


def test_missing_fixture_raises_llm_error(kit: dict[str, Any]) -> None:
    doc: Document = kit["before"]
    clause = _clause(doc, "2.4.2")
    changed = clause.model_copy(update={"text": clause.text + " (правка)"})
    payload = build_payload(doc, None, [changed])
    with pytest.raises(LLMError) as exc:
        extract_functions(doc, None, mock_llm(), clauses=[changed])
    assert mock_fixture_path(payload).name in str(exc.value)
    assert "extract_functions" in str(exc.value)


# --- Проверки кода на подставном LLM ---------------------------------------------------------


def test_foreign_numbers_and_empty_text_dropped(
    kit: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    doc: Document = kit["before"]
    clauses = [_clause(doc, "5.1"), _clause(doc, "5.1.4")]
    llm = FakeLLM(
        {
            "functions": [
                _item(
                    "5.1.4",
                    text="организует контроль устранения недостатков",
                    context_clause_numbers=["5.1", "77.7"],
                ),
                _item("99.99", text="выдуманная функция"),
                _item("5.1.2", text="пункт есть в документе, но не передан модели"),
                _item("5.1.4", text="   "),
            ]
        }
    )
    with caplog.at_level(logging.WARNING, logger="app.functions"):
        functions, constraints = extract_functions(doc, None, llm, clauses=clauses)
    assert constraints == []
    assert [fn.text for fn in functions] == ["организует контроль устранения недостатков"]
    assert functions[0].context_clause_numbers == ["5.1"]
    assert "99.99" in caplog.text and "77.7" in caplog.text and "5.1.2" in caplog.text


def test_code_prohibition_beats_model_modality(kit: dict[str, Any]) -> None:
    doc: Document = kit["before"]
    clause = _clause(doc, "5.9.3")  # под «5.9. Главный аудитор и работники БВА не имеют права:»
    llm = FakeLLM(
        {"functions": [_item("5.9.3", text="подписывать платежные документы", modality="duty")]}
    )
    functions, constraints = extract_functions(doc, None, llm, clauses=[clause])
    assert functions == []
    assert [fn.modality for fn in constraints] == ["prohibition"]
    assert constraints[0].executor == "Главный аудитор и работники БВА"
    assert constraints[0].context_clause_numbers == ["5.9"]


def test_empty_executor_filled_from_lead_in(kit: dict[str, Any]) -> None:
    before, after = kit["before"], kit["after"]
    cases = [
        (before, "5.1.4", "Главный аудитор"),  # вводная без номера «Главный аудитор:»
        (after, "5.3.2.а", "Директоры департаментов и Директоры направлений ДИТААД и ДОА"),
        (after, "4.4.а", "БВА"),  # «…, БВА:» в конце пункта-родителя
        (before, "5.11.1", "Общество"),  # «Для выполнения …, Общество обеспечивает:»
        (before, "5.2", "Главный аудитор"),  # пункт-вводная сам называет исполнителя
    ]
    for doc, number, executor in cases:
        clear_cache()
        llm = FakeLLM({"functions": [_item(number, executor=None)]})
        functions, constraints = extract_functions(doc, None, llm, clauses=[_clause(doc, number)])
        (fn,) = functions + constraints
        assert fn.executor == executor, number
    llm = FakeLLM({"functions": [_item("2.4.2", executor=None)]})
    (fn,), _ = extract_functions(before, None, llm, clauses=[_clause(before, "2.4.2")])
    assert fn.executor is None  # «внутренний аудит осуществляет …» — ни должности, ни подразделения


def test_repeat_call_served_from_cache(kit: dict[str, Any]) -> None:
    doc: Document = kit["before"]
    clauses = [_clause(doc, "2.4.2"), _clause(doc, "2.4.9")]
    llm = FakeLLM({"functions": [_item("2.4.2", text="проведение проверок")]})
    first = extract_functions(doc, None, llm, clauses=clauses)
    second = extract_functions(doc, None, llm, clauses=list(reversed(clauses)))
    assert llm.calls == 1
    assert first == second


def test_repeat_call_does_not_reach_openai(
    kit: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    doc: Document = kit["after"]
    calls: list[str] = []

    def fake_complete_json(self: LLM, name: str, system: str, user: str, schema: Any) -> Any:
        calls.append(name)
        return {"functions": [_item("2.4.10", text="последующий контроль")]}

    monkeypatch.setattr(LLM, "complete_json", fake_complete_json)
    llm = LLM(Settings(llm_mode="live", openai_api_key="test-key-not-used"))
    for _ in range(3):
        functions, _ = extract_functions(doc, None, llm, clauses=[_clause(doc, "2.4.10")])
        assert [fn.text for fn in functions] == ["последующий контроль"]
    assert calls == ["extract_functions"]


def test_schema_violation_is_llm_error(kit: dict[str, Any]) -> None:
    doc: Document = kit["before"]
    llm = FakeLLM({"functions": [{"text": "без обязательных полей"}]})
    with pytest.raises(LLMError):
        extract_functions(doc, None, llm, clauses=[_clause(doc, "2.4.2")])
    llm = FakeLLM({"functions": [_item("2.4.2", category="функция")]})  # не английский enum
    with pytest.raises(LLMError):
        extract_functions(doc, None, llm, clauses=[_clause(doc, "2.4.2")])


def test_function_fields(kit: dict[str, Any]) -> None:
    doc: Document = kit["before"]
    unit: Unit = kit["units_before"][0]
    llm = FakeLLM(
        {
            "functions": [
                _item(
                    "2.4.9",
                    text="мониторинг выполнения планов",
                    category="function",
                    executor="БВА",
                )
            ]
        }
    )
    (fn,), _ = extract_functions(doc, unit, llm, clauses=[_clause(doc, "2.4.9")])
    assert fn.unit_id == unit.id
    assert fn.category == "function" and fn.executor == "БВА" and fn.modality == "duty"
    assert fn.signature and "|" in fn.signature
    assert fn.action is None and fn.object is None
    assert fn.context_clause_numbers == ["2.4"]
    assert len(fn.id) == 12


# --- Вход модели и схема ---------------------------------------------------------------------


def test_payload_sorted_by_index_and_hash_stable(kit: dict[str, Any]) -> None:
    doc: Document = kit["after"]
    clauses = function_clauses(doc)[:12]
    shuffled = clauses[:]
    random.Random(7).shuffle(shuffled)
    unit = kit["units_after"][0]
    payload = build_payload(doc, unit, shuffled)
    assert payload == build_payload(doc, unit, clauses)
    assert mock_fixture_path(payload) == mock_fixture_path(build_payload(doc, unit, clauses))
    assert payload["version"] == "after" and payload["unit"] == unit.name
    first = payload["clauses"][0]
    assert set(first) == {"number", "text", "section_path", "lead_in", "modality"}
    assert [c["number"] for c in payload["clauses"]] == [c.number for c in clauses]


def test_strict_schema_matches_spec() -> None:
    schema = strict_schema(ExtractFunctionsOut)
    item = schema["$defs"]["ExtractedFunction"]
    assert item["additionalProperties"] is False
    assert set(item["required"]) == {
        "text",
        "category",
        "executor",
        "modality",
        "clause_number",
        "context_clause_numbers",
    }
    assert set(item["properties"]["category"]["enum"]) == {
        "task",
        "function",
        "right",
        "duty",
        "responsibility",
    }
    assert set(item["properties"]["modality"]["enum"]) == {
        "duty",
        "right",
        "prohibition",
        "neutral",
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Главный аудитор:", "Главный аудитор"),
        ("5.9. Главный аудитор и работники БВА не имеют права:", "Главный аудитор и работники БВА"),
        (
            "Директоры департаментов и Директоры направлений ДИТААД и ДОА:",
            "Директоры департаментов и Директоры направлений ДИТААД и ДОА",
        ),
        (
            "Директор департамента контроля качества аудита и методологии (далее Директор ДККМ):",
            "Директор департамента контроля качества аудита и методологии",
        ),
        ("Директор ДНМ обязан обеспечить выполнение задач, а также имеет право:", "Директор ДНМ"),
        ("Для выполнения возложенных на БВА задач и функций, Общество обеспечивает:", "Общество"),
        ("Организует работу БВА, осуществляя общее руководство:", None),
        ("Для решения задач внутренний аудит осуществляет следующие функции:", None),
        (None, None),
    ],
)
def test_executor_phrase(text: str | None, expected: str | None) -> None:
    assert executor_phrase(text) == expected
