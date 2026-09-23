"""S01: дымовой тест контракта — эндпоинты spec §4 отвечают валидными по схемам объектами.

Асинхронный контракт (S01 + S08): POST создаёт запуск и сразу отвечает 201 {run_id}, анализ
идёт в фоне. GET статуса в любой момент — валидный RunStatus; итог — done | partial | error.
Отчёт — 200 и валидный Report после done/partial, 404 `run_failed` после error; до итога —
404 `report_not_ready` (проверяет test_runs.py: момент до итога тест поймать не может).
"""

import io
import time
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

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


def _docx_bytes(*paragraphs: str) -> bytes:
    """Минимальный настоящий .docx (zip с word/document.xml и нумерованным пунктом): проходит
    проверку содержимого при загрузке (S16) и разбирается парсером S04."""
    texts = paragraphs or ("1.1. Пункт документа.",)
    body = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>' for text in texts
    )
    ns = "http://schemas.openxmlformats.org/"
    parts = {
        "[Content_Types].xml": (
            f'<Types xmlns="{ns}package/2006/content-types">'
            '<Default Extension="rels" '
            'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/></Types>'
        ),
        "_rels/.rels": (
            f'<Relationships xmlns="{ns}package/2006/relationships">'
            f'<Relationship Id="rId1" Target="word/document.xml" '
            f'Type="{ns}officeDocument/2006/relationships/officeDocument"/></Relationships>'
        ),
        "word/document.xml": (
            f'<w:document xmlns:w="{ns}wordprocessingml/2006/main"><w:body>{body}</w:body>'
            "</w:document>"
        ),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, xml in parts.items():
            archive.writestr(name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + xml)
    return buffer.getvalue()


FINAL_STATES = {"done", "partial", "error"}


@pytest.fixture(autouse=True)
def _runtime_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Запуски пишут загруженные файлы и дамп в runtime_dir: в тестах — во временный каталог.
    monkeypatch.setenv("RUNTIME_DIR", str(tmp_path / "runtime"))


def _demo_run(client: TestClient) -> str:
    response = client.post("/api/runs/demo")
    assert response.status_code == 201, response.text
    return RunCreated.model_validate(response.json()).run_id


def _wait_final(client: TestClient, run_id: str, timeout: float = 60.0) -> RunStatus:
    """Опрашивает статус до итога; каждый ответ по дороге — валидный RunStatus этого запуска."""
    deadline = time.monotonic() + timeout
    while True:
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200, response.text
        status = RunStatus.model_validate(response.json())
        assert status.run_id == run_id
        if status.status in FINAL_STATES:
            return status
        if time.monotonic() > deadline:
            pytest.fail(f"запуск {run_id} не дошёл до итога за {timeout} с: {status}")
        time.sleep(0.02)


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


def test_demo_run_status_is_valid_until_final(client: TestClient) -> None:
    run_id = _demo_run(client)
    status = _wait_final(client, run_id)
    if status.status == "error":
        assert status.detail, "ошибка без текста для пользователя"
    else:
        assert status.progress == 100
        # partial — всегда с перечнем невыполненных шагов, done — без них.
        assert bool(status.missing_steps) == (status.status == "partial")


def test_demo_report_follows_run_state(client: TestClient) -> None:
    run_id = _demo_run(client)
    status = _wait_final(client, run_id)
    response = client.get(f"/api/runs/{run_id}/report")
    if status.status == "error":
        assert response.status_code == 404
        body = response.json()
        assert body["error"] == "run_failed" and body["detail"]
        return
    assert response.status_code == 200, response.text
    report = Report.model_validate(response.json())
    assert report.run_id == run_id
    # Обязательные ключи stats есть всегда; модуль может добавить свои счётчики.
    assert set(STATS_KEYS) <= set(report.stats)


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


def test_upload_docx_creates_run(client: TestClient) -> None:
    files = [
        ("before", ("до.docx", _docx_bytes("1.1. До реорганизации."), DOCX[2])),
        ("after", ("после.docx", _docx_bytes("1.1. После реорганизации."), DOCX[2])),
    ]
    response = client.post("/api/runs", files=files)
    assert response.status_code == 201, response.text
    run_id = RunCreated.model_validate(response.json()).run_id
    status = _wait_final(client, run_id)
    # Свои документы в mock без фикстур — честный error с текстом, а не зависший запуск.
    if status.status == "error":
        assert status.detail


def test_broken_docx_is_honest_error(client: TestClient) -> None:
    files = [("before", ("до.docx", *DOCX[1:])), ("after", ("после.docx", *DOCX[1:]))]
    response = client.post("/api/runs", files=files)
    if response.status_code == 422:
        # Проверка содержимого при загрузке (S16): {error, detail} с понятным текстом.
        body = response.json()
        assert set(body) == {"error", "detail"} and body["detail"]
    else:
        # Без неё файл не разбирается в фоне: error с именем файла.
        assert response.status_code == 201, response.text
        status = _wait_final(client, RunCreated.model_validate(response.json()).run_id)
        assert status.status == "error" and "до.docx" in (status.detail or "")
    assert client.get("/health").status_code == 200


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
