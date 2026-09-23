"""S01: дымовой тест контракта — эндпоинты spec §4 отвечают валидными по схемам объектами."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.schemas import (
    STATS_KEYS,
    Clause,
    Report,
    RunCreated,
    RunStatus,
    Source,
    Unit,
    empty_stats,
)

SPEC_PATHS = {
    "/health": {"get"},
    "/api/runs": {"post"},
    "/api/runs/demo": {"post"},
    "/api/runs/{run_id}": {"get"},
    "/api/runs/{run_id}/report": {"get"},
    "/api/runs/{run_id}/clauses/{doc_id}/{clause_number}": {"get"},
    "/api/runs/{run_id}/report.md": {"get"},
}

DOCX = (
    "f.docx",
    b"PK\x03\x04 fake",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
)


def _demo_run(client: TestClient) -> str:
    response = client.post("/api/runs/demo")
    assert response.status_code == 201, response.text
    return RunCreated.model_validate(response.json()).run_id


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_mode"] == "mock"
    assert body["version"]


def test_docs_and_openapi_list_all_spec_endpoints(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    for path, methods in SPEC_PATHS.items():
        assert path in paths, f"в /docs нет {path}"
        assert methods <= set(paths[path]), f"{path}: нет методов {methods - set(paths[path])}"


def test_demo_run_status_is_valid_and_queued(client: TestClient) -> None:
    run_id = _demo_run(client)
    response = client.get(f"/api/runs/{run_id}")
    assert response.status_code == 200
    status = RunStatus.model_validate(response.json())
    assert status.run_id == run_id
    assert status.status == "queued"
    assert status.progress == 0
    assert status.missing_steps == []


def test_demo_report_is_valid_empty_report(client: TestClient) -> None:
    run_id = _demo_run(client)
    response = client.get(f"/api/runs/{run_id}/report")
    assert response.status_code == 200
    report = Report.model_validate(response.json())
    assert report.run_id == run_id
    assert report.before_documents == [] and report.after_documents == []
    assert report.unit_changes == [] and report.function_matches == []
    assert report.duplicates == [] and report.conflicts == [] and report.constraints == []
    assert report.recommendations == []
    assert set(report.stats) == set(STATS_KEYS)
    assert all(value == 0 for value in report.stats.values())


def test_report_md_is_markdown(client: TestClient) -> None:
    run_id = _demo_run(client)
    response = client.get(f"/api/runs/{run_id}/report.md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text.startswith("# ")
    assert run_id in response.text


def test_clause_lookup_on_empty_report_is_json_404(client: TestClient) -> None:
    run_id = _demo_run(client)
    response = client.get(f"/api/runs/{run_id}/clauses/d8/3.4")
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == "document_not_found"
    assert isinstance(body["detail"], str) and body["detail"]


def test_unknown_run_is_json_404(client: TestClient) -> None:
    for path in ("/api/runs/nope", "/api/runs/nope/report", "/api/runs/nope/report.md"):
        response = client.get(path)
        assert response.status_code == 404, path
        body = response.json()
        assert body["error"] == "run_not_found"
        assert "nope" in body["detail"]


def test_upload_docx_creates_queued_run(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        files=[("before", ("до.docx", *DOCX[1:])), ("after", ("после.docx", *DOCX[1:]))],
    )
    assert response.status_code == 201, response.text
    run_id = RunCreated.model_validate(response.json()).run_id
    status = RunStatus.model_validate(client.get(f"/api/runs/{run_id}").json())
    assert status.status == "queued"


def test_upload_rejects_non_docx_with_422_json(client: TestClient) -> None:
    response = client.post(
        "/api/runs",
        files=[("before", ("до.pdf", b"%PDF-1.4", "application/pdf")), ("after", DOCX)],
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "unsupported_format"
    assert ".docx" in body["detail"] and "до.pdf" in body["detail"]


def test_upload_rejects_more_than_ten_files_total(client: TestClient) -> None:
    files = [("before", DOCX)] * 6 + [("after", DOCX)] * 5
    response = client.post("/api/runs", files=files)
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "too_many_files"
    assert "10" in body["detail"]


def test_upload_rejects_empty_zone(client: TestClient) -> None:
    response = client.post("/api/runs", files=[("before", DOCX)])
    assert response.status_code == 422
    assert response.json()["error"] == "missing_documents"


def test_upload_rejects_file_over_10mb(client: TestClient) -> None:
    big = ("big.docx", b"0" * (10 * 1024 * 1024 + 1), DOCX[2])
    response = client.post("/api/runs", files=[("before", big), ("after", DOCX)])
    assert response.status_code == 422
    assert response.json()["error"] == "file_too_large"


def test_contract_models_forbid_extra_fields_and_require_sources() -> None:
    source = Source(
        doc_id="d8",
        doc_name="Положение_8.docx",
        version="before",
        clause_id="d8:p231:0",
        clause_number="5.9.1.а",
        quote="цитата",
    )
    unit = Unit(id="u1", name="ДККМ", version="before", parent=None, sources=[source])
    assert unit.sources[0].clause_number == "5.9.1.а"
    with pytest.raises(ValidationError):
        Unit(id="u1", name="ДККМ", version="before", parent=None, sources=[])
    with pytest.raises(ValidationError):
        Source.model_validate({**source.model_dump(), "лишнее": 1})
    with pytest.raises(ValidationError):
        RunStatus(run_id="r", status="matching", progress=0, detail=None, missing_steps=[])  # type: ignore[arg-type]
    clause = Clause(
        id="d8:p1:0",
        number=None,
        section=None,
        section_path=[],
        text="Преамбула",
        index=0,
        lead_in=None,
        modality="neutral",
    )
    assert clause.number is None


def test_report_stats_require_all_keys() -> None:
    base = {
        "run_id": "r",
        "created_at": "2026-09-23T09:00:00Z",
        "before_documents": [],
        "after_documents": [],
        "unit_changes": [],
        "function_matches": [],
        "duplicates": [],
        "conflicts": [],
        "constraints": [],
        "conclusion_md": "",
        "recommendations": [],
    }
    Report.model_validate({**base, "stats": empty_stats()})
    with pytest.raises(ValidationError, match="unverified_candidates"):
        Report.model_validate({**base, "stats": {"units_before": 0}})
