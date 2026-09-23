"""S08: оркестратор прогона и API запусков (LLM_MODE=mock, без ключа).

Настоящий demo-run идёт с теми модулями шагов, что уже влиты: без них он честно завершается
`partial`. Полный путь до `done` и правила пропуска/ошибок проверяются на подменных модулях
шагов (pipeline.MODULES) — так тест не зависит от порядка мержа соседей.
"""

import json
import sys
import time
import types
import typing
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import pipeline, store
from app.config import get_settings
from app.llm import LLMError
from app.main import create_app
from app.schemas import (
    Clause,
    Conflict,
    Document,
    Duplicate,
    Function,
    FunctionMatch,
    Report,
    RunState,
    RunStatus,
    Source,
    Unit,
    UnitChange,
    empty_stats,
)

RUN_STATES = set(typing.get_args(RunState))
ALL_STEPS = [
    "parsing",
    "units",
    "functions",
    "candidates",
    "verification",
    "conflicts",
    "conclusion",
]
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[TestClient]:
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    get_settings.cache_clear()


def wait_final(client: TestClient, run_id: str, timeout: float = 60.0) -> tuple[RunStatus, list]:
    """Опрашивает статус до done/partial/error; возвращает итог и пройденные (status, progress)."""
    seen: list[tuple[str, int]] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200, response.text
        status = RunStatus.model_validate(response.json())
        if not seen or seen[-1] != (status.status, status.progress):
            seen.append((status.status, status.progress))
        if status.status in pipeline.FINAL_STATES:
            return status, seen
        time.sleep(0.02)
    pytest.fail(f"прогон {run_id} не завершился за {timeout} с: {seen}")


def assert_honest_report(report: Report) -> None:
    """Инварианты отчёта: источники у каждой находки, запреты отдельно, счётчик непроверенных."""
    for finding in (*report.unit_changes, *report.function_matches, *report.conflicts):
        assert finding.sources, f"находка без источника: {finding.id}"
    for constraint in report.constraints:
        assert constraint.sources and constraint.modality == "prohibition"
    for duplicate in report.duplicates:
        assert duplicate.function_a.sources and duplicate.function_b.sources
    for match in report.function_matches:
        for fn in (*match.before, *match.after):
            assert fn.modality != "prohibition", f"запрет {fn.id} в function_matches"
    unverified = sum(
        1
        for finding in (*report.function_matches, *report.duplicates, *report.conflicts)
        if not finding.verified
    )
    assert "unverified_candidates" in report.stats
    assert report.stats["unverified_candidates"] == unverified


# --- подменные модули шагов ---------------------------------------------------------------


def clause(doc: str, number: str, text: str, index: int, modality: str = "duty") -> Clause:
    return Clause(
        id=f"{doc}:p{index}:0",
        number=number,
        section="2. Цели, задачи и функции",
        section_path=["2. Цели, задачи и функции"],
        text=text,
        index=index,
        lead_in=None,
        modality=modality,
    )


def make_doc(doc_id: str, name: str, version: str) -> Document:
    return Document(
        id=doc_id,
        name=name,
        version=version,
        kind="polozhenie",
        clauses=[
            clause(doc_id, "1.1", "Блок внутреннего аудита (БВА) подотчётен Совету.", 0, "neutral"),
            clause(doc_id, "2.4.1", "БВА проводит аудит процессов управления рисками.", 1),
            clause(doc_id, "2.4.2", "БВА оценивает систему внутреннего контроля.", 2),
            clause(doc_id, "5.9.1", "Работники БВА не имеют права осуществлять закупки.", 3),
        ],
    )


def src(doc: Document, number: str) -> Source:
    found = next(c for c in doc.clauses if c.number == number)
    return Source(
        doc_id=doc.id,
        doc_name=doc.name,
        version=doc.version,
        clause_id=found.id,
        clause_number=number,
        quote=found.text,
    )


def fn(doc: Document, fid: str, number: str, unit_id: str, modality: str = "duty") -> Function:
    return Function(
        id=fid,
        unit_id=unit_id,
        text=next(c.text for c in doc.clauses if c.number == number),
        category="function",
        modality=modality,
        executor="БВА",
        action=None,
        object=None,
        signature=None,
        context_clause_numbers=[],
        sources=[src(doc, number)],
    )


def fake_modules(monkeypatch: pytest.MonkeyPatch, calls: dict, **overrides) -> None:
    """Регистрирует подменные модули всех шагов; overrides: роль → функция/None (нет модуля)."""

    def parse_docx(path, version, name=None):
        calls.setdefault("parsed", []).append((name, version))
        return make_doc("d8" if version == "before" else "d9", name or Path(path).name, version)

    def unit(doc: Document, uid: str) -> Unit:
        return Unit(id=uid, name="БВА", version=doc.version, parent=None, sources=[src(doc, "1.1")])

    def detect_units(docs_before, docs_after, llm=None):
        # Как у S05: списки документов каждой версии и LLM прогона.
        before, after = unit(docs_before[0], "u8"), unit(docs_after[0], "u9")
        return [
            UnitChange(
                id="uc1",
                unit_before=before,
                unit_after=after,
                status="kept",
                note="название совпадает",
                sources=[*before.sources, *after.sources],
            )
        ]

    def extract_all(doc, units, llm):
        assert [u.version for u in units] == [doc.version]
        uid = units[0].id
        if doc.version == "before":
            # Запрет пришёл списком функций — оркестратор сам уносит его в constraints.
            return [
                fn(doc, "f1", "2.4.1", uid),
                fn(doc, "f2", "2.4.2", uid),
                fn(doc, "p8", "5.9.1", uid, "prohibition"),
            ], []
        return [fn(doc, "g1", "2.4.1", uid), fn(doc, "g2", "2.4.2", "u-other")], [
            fn(doc, "p9", "5.9.1", uid, "prohibition")
        ]

    def find_candidates(before, after, llm=None, k=5):
        return {f.id: [{"after_id": "g1", "score": 1.0, "reasons": ["lexical"]}] for f in before}

    def find_duplicate_candidates(functions, k=5):
        return [(functions[0], functions[1], 0.7)]

    def verify_matches(before, after, candidates, llm, after_clauses=None):
        assert all(f.modality != "prohibition" for f in before)
        assert after_clauses, "пункты «после» передаются для confirm_loss"
        f1, g1 = before[0], after[0]
        invented = f1.sources[0].model_copy(update={"clause_number": "9.9.9"})
        return [
            FunctionMatch(
                id="m1",
                before=[f1],
                after=[g1],
                kind="one_to_one",
                status="kept",
                verified=True,
                verification="llm",
                confidence=0.9,
                note="та же функция",
                sources=[*f1.sources, *g1.sources],
            ),
            FunctionMatch(
                id="m-invented",
                before=[before[1]],
                after=[],
                kind="one_to_one",
                status="lost",
                verified=True,
                verification="llm",
                confidence=0.85,
                note="выдуманный пункт",
                sources=[invented],
            ),
        ]

    def find_duplicates(functions_by_unit, llm, candidate_pairs=None):
        calls["duplicate_pairs"] = candidate_pairs
        a, b, score = candidate_pairs[0]
        return [
            Duplicate(
                id="d1",
                function_a=a,
                function_b=b,
                similarity=score,
                note="",
                verified=False,
                verification_note="требует проверки: нет ответа",
            )
        ]

    def find_conflicts(functions_by_unit, llm, constraints=None):
        calls["constraints"] = [c.id for c in constraints or []]
        f = functions_by_unit["u9"][0]
        return [
            Conflict(
                id="c1",
                rule_id="a",
                title="Исполняет и контролирует",
                role_pattern="исполнитель+контролёр",
                severity="medium",
                units=["u9"],
                functions=[f],
                explanation="пример",
                verified=True,
                verification_note="",
                sources=f.sources,
            )
        ]

    def build_facts(report):
        return {"findings": len(report.function_matches)}

    def write_conclusion(facts, llm):
        calls["facts"] = facts
        return {"conclusion_md": "Функции сохранены [F1].", "recommendations": ["Проверить [F2]"]}

    def export_markdown(report):
        return f"# Экспорт отчёта\n\n{report.conclusion_md}\n"

    functions = {
        "parse": {"parse_docx": parse_docx},
        "units": {"detect_units": detect_units},
        "functions": {"extract_all": extract_all},
        "candidates": {
            "find_candidates": find_candidates,
            "find_duplicate_candidates": find_duplicate_candidates,
        },
        "matching": {"verify_matches": verify_matches},
        "duplicates": {"find_duplicates": find_duplicates},
        "conflicts": {"find_conflicts": find_conflicts},
        "conclusion": {"build_facts": build_facts, "write_conclusion": write_conclusion},
        "export": {"export_markdown": export_markdown},
    }
    for role, attrs in functions.items():
        name = f"fake_s08_{role}"
        if role in overrides and overrides[role] is None:
            monkeypatch.setitem(pipeline.MODULES, role, f"app.not_merged_{role}")
            continue
        module = types.ModuleType(name)
        for attr, value in {**attrs, **overrides.get(role, {})}.items():
            setattr(module, attr, value)
        monkeypatch.setitem(sys.modules, name, module)
        monkeypatch.setitem(pipeline.MODULES, role, name)


def record_transitions(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, int | None]]:
    """Все смены статуса, которые пайплайн пишет в store (опрос быстрые шаги пропускает)."""
    transitions: list[tuple[str, int | None]] = []
    original = store.update_status

    def update_status(run_id: str, **changes):
        if "status" in changes:
            transitions.append((changes["status"], changes.get("progress")))
        return original(run_id, **changes)

    monkeypatch.setattr(store, "update_status", update_status)
    return transitions


def run_demo(client: TestClient) -> str:
    response = client.post("/api/runs/demo")
    assert response.status_code == 201, response.text
    return response.json()["run_id"]


# --- настоящий demo-run --------------------------------------------------------------------


def test_demo_run_finishes_honestly_with_merged_modules(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    transitions = record_transitions(monkeypatch)
    run_id = run_demo(client)
    status, seen = wait_final(client, run_id)
    assert {s for s, _ in seen} | {s for s, _ in transitions} <= RUN_STATES
    assert [p for _, p in seen] == sorted(p for _, p in seen), f"прогресс назад: {seen}"
    if status.status == "error" and "Нет фикстуры" in (status.detail or ""):
        pytest.xfail(f"фикстуры соседей ещё не совпадают с разбором: {status.detail}")
    assert status.status in ("done", "partial"), status.detail
    assert status.progress == 100
    passed = {s for s, _ in transitions} | set(status.missing_steps)
    assert {"candidates", "verification"} <= passed, transitions

    response = client.get(f"/api/runs/{run_id}/report")
    assert response.status_code == 200, response.text
    report = Report.model_validate(response.json())
    assert_honest_report(report)
    assert report.stats["skipped"] == len(status.missing_steps)
    if status.status == "partial":
        # Пропущенный модуль виден, а не молча: шаг в missing_steps, причина в detail.
        assert status.missing_steps and set(status.missing_steps) <= set(ALL_STEPS)
        assert "не выполнены шаги" in (status.detail or "")
        assert "не сформировано" in report.conclusion_md.lower()
    else:
        assert status.missing_steps == []

    md = client.get(f"/api/runs/{run_id}/report.md")
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    assert md.text.startswith("# ")


# --- полный путь и правила пропуска на подменных модулях ------------------------------------


def test_all_steps_present_gives_done(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict = {}
    fake_modules(monkeypatch, calls)
    transitions = record_transitions(monkeypatch)
    run_id = run_demo(client)
    status, _ = wait_final(client, run_id)
    assert status.status == "done", status.detail
    assert status.missing_steps == [] and status.progress == 100
    assert transitions == [
        *zip(ALL_STEPS, [5, 15, 30, 45, 65, 80, 90], strict=True),
        ("done", 100),
    ]

    report = Report.model_validate(client.get(f"/api/runs/{run_id}/report").json())
    assert_honest_report(report)
    assert [d.id for d in report.before_documents] == ["d8"]
    by_id = {m.id: m for m in report.function_matches}
    # Выдуманный пункт 9.9.9 отброшен, f2 без решения проверки — непроверенный кандидат.
    assert "m-invented" not in by_id
    assert by_id["m1"].verified and by_id["m1"].status == "kept"
    assert not by_id["unverified-f2"].verified and "требует проверки" in by_id["unverified-f2"].note
    assert sorted(c.id for c in report.constraints) == ["p8", "p9"]
    assert calls["constraints"] == ["p9"]
    assert calls["duplicate_pairs"] and calls["facts"] == {"findings": 2}
    assert report.conclusion_md == "Функции сохранены [F1]."
    assert report.recommendations == ["Проверить [F2]"]
    stats = report.stats
    assert (stats["kept"], stats["lost"], stats["conflicts"], stats["duplicates"]) == (1, 0, 1, 0)
    assert stats["unverified_candidates"] == 2 and stats["skipped"] == 0
    assert (stats["units_before"], stats["units_kept"], stats["functions_before"]) == (1, 1, 2)
    assert stats["constraints"] == 2

    md = client.get(f"/api/runs/{run_id}/report.md")
    assert md.text.startswith("# Экспорт отчёта") and run_id in md.text

    found = client.get(f"/api/runs/{run_id}/clauses/d8/2.4.1")
    assert found.status_code == 200
    assert Clause.model_validate(found.json()).text.startswith("БВА проводит аудит")
    missing = client.get(f"/api/runs/{run_id}/clauses/d8/9.9.9")
    assert missing.status_code == 404 and missing.json()["error"] == "clause_not_found"


def test_missing_candidates_module_is_partial_with_unverified_functions(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_modules(monkeypatch, {}, candidates=None)
    run_id = run_demo(client)
    status, _ = wait_final(client, run_id)
    assert status.status == "partial"
    assert status.missing_steps == ["candidates", "verification", "conclusion"]
    assert "app.not_merged_candidates ещё не реализован" in (status.detail or "")

    report = Report.model_validate(client.get(f"/api/runs/{run_id}/report").json())
    assert_honest_report(report)
    # Без проверки все функции «до» — непроверенные кандидаты, а не выводы о потере.
    assert sorted(m.id for m in report.function_matches) == ["unverified-f1", "unverified-f2"]
    assert all(not m.verified for m in report.function_matches)
    assert "app.not_merged_candidates" in report.function_matches[0].note
    assert report.stats["unverified_candidates"] == report.stats["functions_before"] == 2
    assert report.stats["lost"] == 0 and report.stats["skipped"] == 3
    assert report.conflicts, "конфликты от кандидатов не зависят"
    assert "не сформировано" in report.conclusion_md.lower()
    assert report.recommendations == []


def test_without_parser_report_is_empty_but_valid(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_modules(monkeypatch, {}, parse=None)
    run_id = run_demo(client)
    status, _ = wait_final(client, run_id)
    assert status.status == "partial" and status.missing_steps == ALL_STEPS
    report = Report.model_validate(client.get(f"/api/runs/{run_id}/report").json())
    assert report.before_documents == [] and report.function_matches == []
    assert report.stats["skipped"] == len(ALL_STEPS)
    assert "не сформировано" in report.conclusion_md.lower()


def test_broken_import_inside_module_is_error(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_modules(monkeypatch, {})
    (tmp_path / "broken_s08_units.py").write_text("import definitely_missing_dependency_s08\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setitem(pipeline.MODULES, "units", "broken_s08_units")
    run_id = run_demo(client)
    status, _ = wait_final(client, run_id)
    assert status.status == "error"
    assert (
        "не загружается" in status.detail and "definitely_missing_dependency_s08" in status.detail
    )
    report = client.get(f"/api/runs/{run_id}/report")
    assert report.status_code == 404 and report.json()["error"] == "run_failed"


def test_missing_mock_fixture_is_error_with_key_hint(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def detect_units(docs_before, docs_after, llm=None):
        raise LLMError("no mock fixture (ожидался файл /srv/app/mocks/extract_units/0a1b2c.json)")

    fake_modules(monkeypatch, {}, units={"detect_units": detect_units})
    run_id = run_demo(client)
    status, _ = wait_final(client, run_id)
    assert status.status == "error"
    assert "Нет фикстуры mocks/extract_units/0a1b2c.json" in status.detail
    assert "ключ OpenAI в .env" in status.detail
    assert "units" in status.missing_steps


def test_step_exception_is_partial_and_process_survives(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def find_conflicts(functions_by_unit, llm, constraints=None):
        raise KeyError("u9")

    fake_modules(monkeypatch, {}, conflicts={"find_conflicts": find_conflicts})
    run_id = run_demo(client)
    status, _ = wait_final(client, run_id)
    assert status.status == "partial"
    assert status.missing_steps == ["conflicts", "conclusion"]
    assert "завершился ошибкой (KeyError" in status.detail
    assert client.get("/health").status_code == 200


# --- API ------------------------------------------------------------------------------------


def test_report_is_404_until_finished(client: TestClient) -> None:
    status = RunStatus(run_id="busy", status="units", progress=15, detail=None, missing_steps=[])
    report = Report(
        run_id="busy",
        created_at="2026-09-23T10:00:00Z",
        before_documents=[],
        after_documents=[],
        unit_changes=[],
        function_matches=[],
        duplicates=[],
        conflicts=[],
        constraints=[],
        conclusion_md="",
        recommendations=[],
        stats=empty_stats(),
    )
    store.put("busy", store.RunRecord(status=status, report=report))
    response = client.get("/api/runs/busy/report")
    assert response.status_code == 404
    assert response.json()["error"] == "report_not_ready"
    assert "отчёт ещё не готов" in response.json()["detail"].lower()


def test_upload_rejects_pdf_as_not_supported(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        files=[
            ("before[]", ("до.pdf", b"%PDF-1.4", "application/pdf")),
            ("after[]", ("после.docx", b"PK\x03\x04", DOCX_MIME)),
        ],
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "unsupported_format"
    assert "не поддержан" in body["detail"] and "до.pdf" in body["detail"]


def test_upload_with_bracket_fields_saves_files_and_runs(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: dict = {}
    fake_modules(monkeypatch, calls)
    response = client.post(
        "/api/runs",
        files=[
            ("before[]", ("../до.docx", b"PK\x03\x04 before", DOCX_MIME)),
            ("after[]", ("после.docx", b"PK\x03\x04 after", DOCX_MIME)),
        ],
    )
    assert response.status_code == 201, response.text
    run_id = response.json()["run_id"]
    status, _ = wait_final(client, run_id)
    assert status.status == "done", status.detail
    assert calls["parsed"] == [("до.docx", "before"), ("после.docx", "after")]
    saved = store.run_dir(run_id)
    assert (saved / "before" / "01_до.docx").read_bytes() == b"PK\x03\x04 before"
    assert (saved / "after" / "01_после.docx").is_file()
    assert (saved.parent / f"{run_id}.json").is_file(), "дамп запуска в runtime_dir"


# --- проверка источников: цитата, clause_id, обе стороны находки -------------------------


def _match(mid: str, before: list[Function], after: list[Function], sources: list[Source]):
    return FunctionMatch(
        id=mid,
        before=before,
        after=after,
        kind="one_to_one",
        status="kept" if after else "lost",
        verified=True,
        verification="llm",
        confidence=0.9,
        note="",
        sources=sources,
    )


def test_source_check_verifies_quote_clause_id_and_both_sides(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def verify_matches(before, after, candidates, llm, after_clauses=None):
        f1, f2 = before[0], before[1]
        g1, g2 = after[0], after[1]
        real = f1.sources[0]  # d8, п. 2.4.1
        fake_quote = real.model_copy(update={"quote": "БВА согласует все закупки компании."})
        foreign_id = real.model_copy(update={"clause_id": f2.sources[0].clause_id})
        # Типографика, неразрывный пробел, пропуск «…» и точка в конце — та же цитата.
        loose = real.model_copy(update={"quote": "«БВА\u00a0проводит аудит … управления рисками»."})
        g1_fake = g1.model_copy(
            update={"sources": [g1.sources[0].model_copy(update={"quote": "Выдуманный текст."})]}
        )
        f2_cites_after = f2.model_copy(update={"sources": g2.sources})
        return [
            _match("m-fake-quote", [f1], [g1], [fake_quote]),
            _match("m-foreign-clause-id", [f1], [g1], [foreign_id]),
            _match("m-fake-after-side", [f1], [g1_fake], [*f1.sources, *g1.sources]),
            _match("m-before-side-cites-after", [f2_cites_after], [g2], [*f2.sources, *g2.sources]),
            _match("m-loose-quote", [f1], [g1], [loose, *g1.sources]),
        ]

    fake_modules(monkeypatch, {}, matching={"verify_matches": verify_matches})
    run_id = run_demo(client)
    status, _ = wait_final(client, run_id)
    assert status.status == "done", status.detail
    report = Report.model_validate(client.get(f"/api/runs/{run_id}/report").json())
    assert_honest_report(report)
    by_id = {m.id: m for m in report.function_matches}
    # Существующий номер пункта не спасает выдуманную цитату, чужой clause_id и сторону
    # без подтверждённого источника; такие находки не показываются.
    assert set(by_id) == {"m-loose-quote", "unverified-f2"}
    assert by_id["m-loose-quote"].verified and not by_id["unverified-f2"].verified


def test_unit_change_side_without_confirmed_source_is_dropped(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def detect_units(docs_before, docs_after, llm=None):
        b, a = docs_before[0], docs_after[0]
        u8 = Unit(id="u8", name="БВА", version="before", parent=None, sources=[src(b, "1.1")])
        u9 = Unit(id="u9", name="БВА", version="after", parent=None, sources=[src(a, "1.1")])
        invented = src(a, "1.1").model_copy(update={"quote": "Отдел закупок подчиняется БВА."})
        fake = Unit(
            id="u-fake", name="Отдел закупок", version="after", parent=None, sources=[invented]
        )
        return [
            UnitChange(
                id="uc1",
                unit_before=u8,
                unit_after=u9,
                status="kept",
                note="",
                sources=[*u8.sources, *u9.sources],
            ),
            # У самой находки источник настоящий, у подразделения «после» — выдуманная цитата.
            UnitChange(
                id="uc-fake",
                unit_before=None,
                unit_after=fake,
                status="created",
                note="",
                sources=[src(a, "1.1")],
            ),
        ]

    fake_modules(monkeypatch, {}, units={"detect_units": detect_units})
    run_id = run_demo(client)
    status, _ = wait_final(client, run_id)
    assert status.status == "done", status.detail
    report = Report.model_validate(client.get(f"/api/runs/{run_id}/report").json())
    assert [c.id for c in report.unit_changes] == ["uc1"]


# --- несколько документов в версии: интерфейс S05/S08 -------------------------------------


class StubLLM:
    """«Живая» LLM без сети: ответ extract_units по пунктам, которые пришли в запросе."""

    mode = "live"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete_json(self, name: str, system: str, user: str, schema: dict) -> dict:
        self.calls.append(name)
        assert name == "extract_units", f"неожиданный вызов LLM: {name}"
        numbers = [c["number"] for c in json.loads(user)["clauses"]]
        assert "1.1" in numbers
        unit = {"name": "Блок внутреннего аудита (БВА)", "parent": "", "clause_numbers": ["1.1"]}
        return {"units": [unit]}


def test_several_documents_per_version_reach_units_step(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def parse_docx(path, version, name=None):
        return make_doc(f"d-{Path(name).stem}", name, version)

    llm = StubLLM()
    fake_modules(
        monkeypatch,
        {},
        parse={"parse_docx": parse_docx},
        **dict.fromkeys(
            ("functions", "candidates", "matching", "duplicates", "conflicts", "conclusion"),
            None,
        ),
    )
    monkeypatch.setitem(pipeline.MODULES, "units", "app.units")  # настоящий S05
    monkeypatch.setattr(pipeline, "LLM", lambda settings=None: llm)
    response = client.post(
        "/api/runs",
        files=[
            ("before[]", ("положение.docx", b"PK\x03\x04 a", DOCX_MIME)),
            ("before[]", ("ди.docx", b"PK\x03\x04 b", DOCX_MIME)),
            ("after[]", ("положение-9.docx", b"PK\x03\x04 c", DOCX_MIME)),
        ],
    )
    assert response.status_code == 201, response.text
    run_id = response.json()["run_id"]
    status, _ = wait_final(client, run_id)
    assert status.status == "partial", status.detail
    assert "units" not in status.missing_steps, status.detail
    assert "has no attribute" not in (status.detail or "")
    assert llm.calls == ["extract_units"] * 3  # по вызову на документ, match_units не нужен

    report = Report.model_validate(client.get(f"/api/runs/{run_id}/report").json())
    assert [d.id for d in report.before_documents] == ["d-положение", "d-ди"]
    [change] = report.unit_changes
    assert change.status == "kept"
    # Одно подразделение «до» из двух документов — с источниками обоих.
    assert {s.doc_id for s in change.unit_before.sources} == {"d-положение", "d-ди"}
    assert {s.doc_id for s in change.unit_after.sources} == {"d-положение-9"}
