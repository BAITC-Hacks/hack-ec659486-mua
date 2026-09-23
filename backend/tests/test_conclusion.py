"""S14: факты, фикстура заключения и Markdown-экспорт демо-отчёта."""

import json
import re
from pathlib import Path

import pytest

from app import conclusion
from app.conclusion import build_facts, write_conclusion
from app.config import Settings
from app.export_md import _all_sources, export_markdown
from app.llm import LLM, LLMError
from app.schemas import Report

DEMO = Path(__file__).resolve().parents[1] / "app" / "mocks" / "demo_report.json"


@pytest.fixture
def report() -> Report:
    return Report.model_validate_json(DEMO.read_text(encoding="utf-8"))


@pytest.fixture
def mock_llm() -> LLM:
    return LLM(Settings(llm_mode="mock"))


def test_build_facts_are_sourced_and_numbered(report: Report) -> None:
    facts = build_facts(report)
    all_facts = facts["findings"] + facts["unverified"]
    assert all_facts
    assert all(item["sources"] for item in all_facts)
    assert sorted(int(item["id"][1:]) for item in all_facts) == list(range(1, len(all_facts) + 1))
    assert {item["status"] for item in facts["unverified"]} >= {"lost", "duplicate", "conflict"}
    assert facts["constraints"]
    assert facts["stats"]["unverified_candidates"] == len(facts["unverified"])


def test_write_conclusion_uses_fixture_and_known_refs(report: Report, mock_llm: LLM) -> None:
    facts = build_facts(report)
    out = write_conclusion(facts, mock_llm)
    known = {item["id"] for item in facts["findings"] + facts["unverified"]}
    assert "### Подтверждённые находки" in out.conclusion_md
    assert "### Требует проверки" in out.conclusion_md
    interpretation = out.conclusion_md.split("### Интерпретация\n\n", 1)[1]
    for paragraph in interpretation.split("\n\n")[:-1]:
        refs = {"F" + number for number in re.findall(r"\[F(\d+)\]", paragraph)}
        assert refs and refs <= known
    assert out.recommendations
    assert all(re.search(r"\[F\d+\]", item) for item in out.recommendations)


def test_unknown_reference_paragraph_is_discarded(
    report: Report, mock_llm: LLM, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    facts = build_facts(report)
    path = tmp_path / "fake.json"
    path.write_text(
        json.dumps(
            {
                "conclusion_md": "Допустимый вывод. [F2]\n\nВыдуманная находка. [F99]",
                "recommendations": ["Уточнить закрепление функций. [F2]"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(conclusion, "_fixture_path", lambda _: path)
    out = write_conclusion(facts, mock_llm)
    assert "Допустимый вывод" in out.conclusion_md
    assert "Выдуманная находка" not in out.conclusion_md


def test_empty_findings_skip_llm(mock_llm: LLM, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*_: object, **__: object) -> None:
        raise AssertionError("LLM не должен вызываться")

    monkeypatch.setattr(mock_llm, "complete_json", fail)
    out = write_conclusion({"findings": [], "unverified": []}, mock_llm)
    assert "существенных изменений по документам не найдено" in out.conclusion_md.lower()
    assert out.recommendations == []


def test_missing_fixture_is_error(
    report: Report, mock_llm: LLM, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(conclusion, "_fixture_path", lambda _: tmp_path / "missing.json")
    with pytest.raises(LLMError, match="missing.json"):
        write_conclusion(build_facts(report), mock_llm)


def test_markdown_has_sections_and_every_source(report: Report) -> None:
    markdown = export_markdown(report)
    for heading in (
        "Сводка",
        "Подразделения",
        "Функции",
        "Кандидаты в потери — требует проверки",
        "Ограничения",
        "Дубли",
        "Конфликты интересов",
        "Заключение",
        "Рекомендации",
        "Источники",
    ):
        assert f"## {heading}" in markdown
    for source in _all_sources(report):
        assert source.clause_number in markdown if source.clause_number else True
        assert source.quote in markdown
    assert "PDF и Excel в прототипе не поддержаны" in markdown
