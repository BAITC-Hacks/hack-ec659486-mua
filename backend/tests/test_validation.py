"""Валидация содержимого .docx не меняет коды ошибок загрузки S08."""

import asyncio
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from fastapi.testclient import TestClient

from app import validation

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def docx_bytes(text: str = "1.1. Тестовый пункт.") -> bytes:
    content = BytesIO()
    with ZipFile(content, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.'
            'main+xml"/></Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>",
        )
    return content.getvalue()


def upload(client: TestClient, name: str, content: bytes):
    return client.post(
        "/api/runs",
        files=[
            ("before", (name, content, DOCX_MIME)),
            ("after", ("после.docx", docx_bytes(), DOCX_MIME)),
        ],
    )


def test_pdf_keeps_s08_error_code(client: TestClient) -> None:
    response = upload(client, "до.pdf", b"%PDF-1.4")
    assert response.status_code == 422
    assert response.json()["error"] == "unsupported_format"
    assert "не поддержан" in response.json()["detail"]


def test_too_large_keeps_s08_error_code(client: TestClient) -> None:
    response = upload(client, "до.docx", b"0" * (10 * 1024 * 1024 + 1))
    assert response.status_code == 422
    assert response.json()["error"] == "file_too_large"
    assert "10 МБ" in response.json()["detail"]


@pytest.mark.parametrize(
    ("content", "message"),
    [
        (b"not a zip", "повреждён"),
        (docx_bytes("Текст без номера."), "нет нумерованных пунктов"),
    ],
)
def test_bad_docx_content_is_rejected(
    client: TestClient, content: bytes, message: str
) -> None:
    response = upload(client, "до.docx", content)
    assert response.status_code == 422
    assert set(response.json()) == {"error", "detail"}
    assert response.json()["error"] == "validation"
    assert message in response.json()["detail"]


@pytest.mark.asyncio
async def test_timeout_sets_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeStore:
        changes: dict = {}

        def update_status(self, run_id: str, **changes):
            assert run_id == "r"
            self.changes = changes

    fake = FakeStore()
    monkeypatch.setattr(validation, "PIPELINE_TIMEOUT_S", 0.01)
    await validation.with_timeout("r", asyncio.sleep(1), fake)
    assert fake.changes["status"] == "error"
    assert "превысил" in fake.changes["detail"]
