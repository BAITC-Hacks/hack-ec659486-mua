"""P2 «Подразделения до/после» (S05): кандидаты, extract_units, match_units, mock-фикстуры.

Парсер S04 не ждём: `Document` строится здесь из текста тестового комплекта. Текст берётся
из `data/case11/*.docx` тем же путём, что запасной разбор `prebuilt/lib_docx` (zip + xml),
по правилам S04: «3.4. …» → пункт, «а. …» → подпункт «3.4.а» предыдущего пункта,
`section_path` — заголовок раздела и тексты родительских пунктов по номеру, `lead_in` —
текст родителя с двоеточием на конце или ближайшая вводная без номера («Главный аудитор:»).
"""

import html
import re
import zipfile
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter

from app.config import Settings
from app.llm import LLM, LLMError
from app.schemas import Clause, Document, Source, Unit, UnitChange
from app.units import (
    detect_units,
    extract_units,
    find_candidates,
    match_units,
    normalize_name,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "case11"
DOC_BEFORE = "Положение_о_внутреннем_аудите_редакция_8_обезличено.docx"
DOC_AFTER = "Положение_о_внутреннем_аудите_редакция_9_обезличено.docx"


# --- Построение Document из текста (вместо парсера S04) -----------------------------------

_NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)\.\s*(.*)$", re.DOTALL)
_LETTER_RE = re.compile(r"^([а-яё])[.)]\s+(.*)$", re.DOTALL)
_SPLIT_RE = re.compile(r"\s(?=\d+(?:\.\d+)+\.\s?[А-ЯЁA-Z«\"])")
_TOC_RE = re.compile(r"^\d+\.\s+[^a-zа-яё]+\s\d+$")
_PROHIBITION = ("не вправе", "не имеет права", "не имеют права", "запрещается", "не допускается")
_RIGHT = ("имеет право", "имеют право", "вправе")
_DUTY = (
    "осуществляет",
    "обеспечивает",
    "проводит",
    "формирует",
    "представляет",
    "организует",
    "обязан",
    "несет ответственность",
    "несут ответственность",
)


def _docx_lines(path: Path) -> list[str]:
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf-8", "ignore")
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = html.unescape(re.sub(r"<[^>]+>", "", xml))
    return [line.strip() for line in xml.split("\n") if line.strip()]


def _modality(text: str) -> str:
    low = text.lower().replace("ё", "е")
    if any(m in low for m in _PROHIBITION):
        return "prohibition"
    if any(m in low for m in _RIGHT):
        return "right"
    if any(m in low for m in _DUTY):
        return "duty"
    return "neutral"


def build_document(lines: list[str], version: str, doc_id: str, name: str) -> Document:
    clauses: list[Clause] = []
    by_number: dict[str, Clause] = {}
    section = "Преамбула"
    last_numbered: Clause | None = None
    free_lead: str | None = None
    free_level: int | None = None

    def add(number: str | None, text: str, path: list[str], lead: str | None, p: int, k: int):
        mod = _modality(text)
        if lead and mod == "neutral":
            mod = _modality(lead)
        clause = Clause(
            id=f"{doc_id}:p{p}:{k}",
            number=number,
            section=section,
            section_path=path,
            text=text,
            index=len(clauses),
            lead_in=lead,
            modality=mod,
        )
        clauses.append(clause)
        if number:
            by_number.setdefault(number, clause)
        return clause

    for p, line in enumerate(lines):
        if line.lower() == "оглавление":
            break
        if _TOC_RE.match(line):
            continue
        for k, piece in enumerate(_SPLIT_RE.split(line)):
            piece = piece.strip()
            num, letter = _NUM_RE.match(piece), _LETTER_RE.match(piece)
            if num:
                number = num.group(1)
                level = number.count(".") + 1
                if level == 1:
                    section = piece[:200]
                    free_lead, free_level, last_numbered = None, None, None
                    add(number, piece, [section], None, p, k)
                    continue
                parts = number.split(".")
                prefixes = [".".join(parts[: i + 1]) for i in range(len(parts) - 1)]
                path = [section] + [by_number[x].text[:200] for x in prefixes[1:] if x in by_number]
                parent = by_number.get(prefixes[-1])
                lead = parent.text if parent is not None and parent.text.endswith(":") else None
                # вводная без номера («Главный аудитор:») действует на первый пункт после неё
                # и на его вложенные; следующий пункт того же уровня её закрывает
                if free_lead is not None:
                    if free_level is None:
                        free_level = level
                    elif level <= free_level:
                        free_lead, free_level = None, None
                    if free_lead is not None and lead is None:
                        lead = free_lead
                last_numbered = add(number, piece, path, lead, p, k)
            elif letter and last_numbered is not None:
                parent = last_numbered
                path = [*parent.section_path, parent.text[:200]]
                lead = parent.text if parent.text.endswith(":") else None
                add(f"{parent.number}.{letter.group(1)}", piece, path, lead, p, k)
            else:
                lead = free_lead if free_lead and free_level is None else None
                add(None, piece, [section], lead, p, k)
                if piece.endswith(":") and len(piece) <= 80:
                    free_lead, free_level, last_numbered = piece, None, None
    return Document(id=doc_id, name=name, version=version, kind="polozhenie", clauses=clauses)


def load_kit_document(file_name: str, version: str) -> Document:
    path = DATA_DIR / file_name
    doc_id = "case11-before" if version == "before" else "case11-after"
    return build_document(_docx_lines(path), version, doc_id, file_name)


@pytest.fixture(scope="module")
def kit() -> tuple[Document, Document]:
    return (
        load_kit_document(DOC_BEFORE, "before"),
        load_kit_document(DOC_AFTER, "after"),
    )


# --- LLM-заглушки -------------------------------------------------------------------------


class StubLLM:
    """«Живая» LLM с заранее заданными ответами: проверяем код вокруг вызова, без сети."""

    mode = "live"

    def __init__(self, responses: dict[str, dict[str, Any]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[str] = []

    def complete_json(self, name: str, system: str, user: str, schema: dict) -> dict:
        self.calls.append(name)
        assert system.strip(), f"пустой промпт для {name}"
        assert schema.get("additionalProperties") is False
        if name not in self.responses:
            raise AssertionError(f"неожиданный вызов LLM: {name}")
        return self.responses[name]


def mock_llm() -> LLM:
    return LLM(Settings(llm_mode="mock", openai_api_key=None))


def _clause(
    doc_id: str, i: int, number: str | None, text: str, path: list[str], lead_in: str | None = None
) -> Clause:
    return Clause(
        id=f"{doc_id}:p{i}:0",
        number=number,
        section=path[0] if path else None,
        section_path=path,
        text=text,
        index=i,
        lead_in=lead_in,
        modality="neutral",
    )


def small_document(version: str = "after") -> Document:
    """Структура: ДОА с вводной «…:», пункт под заголовком «Департамент …», «Главный аудитор:»."""
    d = f"small-{version}"
    s3 = "3. Структура и организация работы"
    s4 = "4. Департамент информационных технологий"
    s5 = "5. Права и обязанности"
    doa = "3.5. Департамент операционного аудита (ДОА):"
    return Document(
        id=d,
        name=f"{d}.docx",
        version=version,
        kind="polozhenie",
        clauses=[
            _clause(d, 0, "3", s3, [s3]),
            _clause(d, 1, "3.4", "3.4. БВА состоит из следующих структурных подразделений:", [s3]),
            _clause(
                d,
                2,
                "3.4.а",
                "а. Департамент операционного аудита (ДОА).",
                [s3, "3.4. БВА состоит из следующих структурных подразделений:"],
                "3.4. БВА состоит из следующих структурных подразделений:",
            ),
            _clause(d, 3, "3.5", doa, [s3]),
            _clause(
                d, 4, "3.5.1", "3.5.1. проводит проверки операционных процессов;", [s3, doa], doa
            ),
            _clause(d, 5, "4", s4, [s4]),
            _clause(d, 6, "4.1", "4.1. сопровождает информационные системы.", [s4]),
            _clause(d, 7, "5", s5, [s5]),
            _clause(d, 8, None, "Главный аудитор:", [s5]),
            _clause(d, 9, "5.1", "5.1. утверждает годовой план работ;", [s5], "Главный аудитор:"),
        ],
    )


def _unit(uid: str, name: str, version: str) -> Unit:
    src = Source(
        doc_id=f"d-{version}",
        doc_name="x.docx",
        version=version,
        clause_id=f"d-{version}:p1:0",
        clause_number="3.4",
        quote=name,
    )
    return Unit(id=uid, name=name, version=version, parent=None, sources=[src])


def _numbers(unit: Unit) -> list[str | None]:
    return [s.clause_number for s in unit.sources]


# --- Тесты ------------------------------------------------------------------------------


def test_normalize_name() -> None:
    assert normalize_name("Департамента  контроля качества (ДККМ)") == (
        "департамент контроля качества"
    )
    assert normalize_name("Блок внутреннего аудита Общества") == "блок внутреннего аудита"
    assert normalize_name("Отдел учёта") == normalize_name("отдел учета")


def test_deterministic_match_without_llm() -> None:
    before = [
        _unit("b1", "Департамент контроля качества аудита и методологии (ДККМ)", "before"),
        _unit(
            "b2",
            "Департамент непрерывного мониторинга системы внутреннего контроля (ДНМ)",
            "before",
        ),
    ]
    after = [
        _unit("a1", "Департамент непрерывного мониторинга СВК (ДНМ)", "after"),
        _unit("a2", "департамент контроля качества аудита и методологии", "after"),
    ]
    llm = StubLLM()  # любой вызов LLM — AssertionError
    changes = match_units(before, after, llm)
    assert llm.calls == []
    assert [c.status for c in changes] == ["kept", "kept"]
    pairs = {(c.unit_before.id, c.unit_after.id) for c in changes}
    assert pairs == {("b1", "a2"), ("b2", "a1")}
    assert all(len(c.sources) == 2 for c in changes)


def test_one_side_rest_needs_no_llm() -> None:
    before = [_unit("b1", "Отдел кадров", "before")]
    after = [_unit("a1", "Отдел кадров", "after"), _unit("a2", "Служба безопасности", "after")]
    llm = StubLLM()
    changes = match_units(before, after, llm)
    assert llm.calls == []
    assert [(c.status, c.unit_after.id) for c in changes] == [("kept", "a1"), ("created", "a2")]


def test_candidate_from_section_path_and_lead_in() -> None:
    doc = small_document()
    cands = {c.key: c for c in find_candidates(doc).units}
    doa = cands["департамент операционного аудита"]
    assert doa.abbr == "ДОА"
    # «3.5.1. проводит проверки…» — названия нет в тексте, но оно в lead_in/section_path
    assert "small-after:p4:0" in doa.clause_ids
    # «4.1. сопровождает…» — только заголовок раздела «4. Департамент …» в section_path
    it = cands["департамент информационных технологий"]
    assert "small-after:p6:0" in it.clause_ids

    llm = StubLLM(
        {
            "extract_units": {
                "units": [
                    {
                        "name": "Департамент операционного аудита (ДОА)",
                        "parent": "",
                        "clause_numbers": ["3.5"],
                    },
                ]
            }
        }
    )
    units = extract_units(doc, llm)
    assert llm.calls == ["extract_units"]
    assert len(units) == 1
    # пункт 3.5.1 попал в источники из словарного кандидата, 3.4.а — по аббревиатуре
    assert {"3.5", "3.5.1", "3.4.а"} <= set(_numbers(units[0]))


def test_position_from_lead_in_is_not_unit() -> None:
    doc = small_document()
    found = find_candidates(doc)
    positions = {c.key: c for c in found.positions}
    assert "главный аудитор" in positions
    assert "small-after:p9:0" in positions["главный аудитор"].clause_ids
    assert all("аудитор" not in c.key for c in found.units)

    llm = StubLLM(
        {
            "extract_units": {
                "units": [
                    {"name": "Главный аудитор", "parent": "", "clause_numbers": ["5.1"]},
                    {
                        "name": "Департамент операционного аудита (ДОА)",
                        "parent": "",
                        "clause_numbers": ["3.4.а"],
                    },
                ]
            }
        }
    )
    units = extract_units(doc, llm)
    assert [u.name for u in units] == ["Департамент операционного аудита (ДОА)"]


def test_foreign_clause_numbers_dropped(caplog: pytest.LogCaptureFixture) -> None:
    doc = small_document()
    llm = StubLLM(
        {
            "extract_units": {
                "units": [
                    {
                        "name": "Департамент операционного аудита (ДОА)",
                        "parent": "",
                        "clause_numbers": ["3.4.а", "99.9"],
                    },
                    {"name": "Отдел фантомных проверок", "parent": "", "clause_numbers": ["77.7"]},
                ]
            }
        }
    )
    units = extract_units(doc, llm)
    assert [u.name for u in units] == ["Департамент операционного аудита (ДОА)"]
    assert "99.9" not in _numbers(units[0])
    assert "77.7" in caplog.text and "Отдел фантомных проверок" in caplog.text


def test_match_units_pairs_are_validated() -> None:
    before = [_unit("b1", "Направление внутреннего аудита", "before")]
    after = [_unit("a1", "Департамент операционного аудита (ДОА)", "after")]
    llm = StubLLM(
        {
            "match_units": {
                "pairs": [
                    {
                        "before": "Выдуманное направление",
                        "after": "",
                        "status": "abolished",
                        "note": "x",
                    },
                    {
                        "before": "",
                        "after": "Департамент операционного аудита (ДОА)",
                        "status": "kept",
                        "note": "статус не согласуется с пустым before",
                    },
                    {
                        "before": "Направление внутреннего аудита",
                        "after": "",
                        "status": "transformed",
                        "note": "Функции переданы ДОА.",
                    },
                ]
            }
        }
    )
    changes = match_units(before, after, llm)
    assert llm.calls == ["match_units"]
    by_status = {c.status: c for c in changes}
    assert set(by_status) == {"transformed", "created"}
    assert by_status["transformed"].note == "Функции переданы ДОА."
    assert by_status["created"].unit_after.id == "a1"


def test_case11_kit(kit: tuple[Document, Document]) -> None:
    before, after = kit
    result = detect_units(before, after, mock_llm())
    assert result, "подразделения не найдены"
    for change in result:
        assert change.sources, f"{change.id} без источников"
        assert change.note.strip()
        for unit in (change.unit_before, change.unit_after):
            if unit is not None:
                assert unit.sources

    statuses = [c.status for c in result]
    assert statuses.count("created") >= 2
    assert statuses.count("kept") >= 2

    def status_of(abbr_or_name: str) -> set[str]:
        return {
            c.status
            for c in result
            for u in (c.unit_before, c.unit_after)
            if u is not None and abbr_or_name in u.name
        }

    assert status_of("ДНМ") == {"kept"}
    assert status_of("ДККМ") == {"kept"}
    assert status_of("БВА") == {"kept"}
    assert status_of("ДИТААД") == {"created"}
    assert status_of("ДОА") == {"created"}
    assert status_of("Направление внутреннего аудита") <= {"transformed", "abolished"}
    assert status_of("Направление внутреннего аудита")

    # каждая ссылка — реальный пункт своей редакции, цитата дословно из пункта
    texts = {(d.id, c.id): c.text for d in (before, after) for c in d.clauses}
    for change in result:
        for src in change.sources:
            assert src.quote and src.quote in texts[(src.doc_id, src.clause_id)]

    # ДИТААД ред. 9: пункт 3.4.а и подчинённые должности п. 3.6
    ditaad = next(c.unit_after for c in result if c.unit_after and "ДИТААД" in c.unit_after.name)
    assert {"3.4.а", "3.6"} <= set(_numbers(ditaad))

    # должности — отдельно, для executor функций (S09)
    names_before = {p.name for p in result.positions_before}
    assert "Главный аудитор" in names_before
    assert "Директор направления внутреннего аудита" in names_before
    unit_names = {u.name for u in result.units_before + result.units_after}
    assert "Главный аудитор" not in unit_names

    # результат годится как Report.unit_changes (контракт S08)
    TypeAdapter(list[UnitChange]).validate_python(result)


def test_missing_fixture_raises_llm_error() -> None:
    with pytest.raises(LLMError, match=r"mocks/extract_units/[0-9a-f]{16}\.json"):
        detect_units(small_document("before"), small_document("after"), mock_llm())
