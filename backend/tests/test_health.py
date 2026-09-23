import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from app.config import Settings, get_settings
from app.llm import LLM, LLMError, redact_secrets, strict_schema
from app.schemas import ExampleLLMOutput


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_mode"] == "mock"
    assert "version" in body
    assert "model" in body


def test_version(client: TestClient) -> None:
    response = client.get("/api/version")
    assert response.status_code == 200
    body = response.json()
    assert body["llm_mode"] == "mock"
    assert body["version"]
    assert body["name"]


def test_example_returns_mock_fixture(client: TestClient) -> None:
    response = client.post("/api/example", json={"text": "привет"})
    assert response.status_code == 200
    body = response.json()
    assert body == {"answer": "mock", "llm_mode": "mock"}


def test_example_validation_error_is_json(client: TestClient) -> None:
    response = client.post("/api/example", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    assert isinstance(body["detail"], list)


def test_example_rejects_empty_text(client: TestClient) -> None:
    response = client.post("/api/example", json={"text": ""})
    assert response.status_code == 422


def test_not_found_is_json(client: TestClient) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"] == "http_error"


def test_missing_mock_fixture_raises(client: TestClient) -> None:
    llm = LLM(get_settings())
    assert llm.mode == "mock"
    with pytest.raises(LLMError, match="no mock fixture"):
        llm.complete_json("does_not_exist", "system", "user", {})


def test_live_without_key_refuses_to_start() -> None:
    """Явный live с пустым ключом — ошибка конфигурации, а не тихий mock (Положение 5.6.6).

    _env_file=None обязателен: без него pydantic-settings прочитает личный .env
    разработчика, там окажется настоящий ключ, и тест позеленеет по ошибке.
    """
    settings = Settings(_env_file=None, llm_mode="live", openai_api_key=None)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        settings.check_startup()


def test_live_mode_is_not_silently_downgraded() -> None:
    settings = Settings(_env_file=None, llm_mode="live", openai_api_key="sk-test-not-a-real-key")
    assert settings.effective_llm_mode == "live"
    settings.check_startup()  # с ключом старт разрешён


def test_mock_mode_needs_no_key() -> None:
    settings = Settings(_env_file=None, llm_mode="mock", openai_api_key=None)
    assert settings.effective_llm_mode == "mock"
    settings.check_startup()


def test_llm_output_rejects_extra_fields() -> None:
    """strict_schema обещает additionalProperties=false — локальная проверка обязана совпадать."""
    with pytest.raises(PydanticValidationError):
        ExampleLLMOutput.model_validate({"answer": "ok", "лишнее": 1})


def test_invalid_llm_output_becomes_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Невалидный ответ модели — ошибка внешней системы (502), а не наша (500)."""
    from app import llm as llm_module

    def broken(self: LLM, name: str, system: str, user: str, schema: dict) -> dict:  # noqa: ANN401
        return {"answer": "ok", "лишнее": "поле"}

    monkeypatch.setattr(llm_module.LLM, "complete_json", broken)
    response = client.post("/api/example", json={"text": "привет"})
    assert response.status_code == 502
    assert response.json()["error"] == "llm_error"


def test_internal_error_does_not_leak_exception_text(client: TestClient) -> None:
    """500 не раскрывает внутренности: клиент получает постоянный текст и ref."""
    app = client.app
    assert isinstance(app, FastAPI)

    @app.get("/api/_boom")
    def _boom() -> None:
        raise ValueError("секрет sk-liveKEY0123456789 и /внутренний/путь")

    with TestClient(app, raise_server_exceptions=False) as c:
        response = c.get("/api/_boom")
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_error"
    assert body["detail"] == "Внутренняя ошибка сервера."
    assert "sk-" not in response.text
    assert "ValueError" not in response.text
    assert len(body["ref"]) == 8


def test_redact_secrets_hides_api_keys() -> None:
    assert "sk-" not in redact_secrets("Error code: 401, key sk-proj-AbCd1234EfGh is invalid")
    assert redact_secrets("нет ключей") == "нет ключей"


def test_strict_schema_shape() -> None:
    schema = strict_schema(ExampleLLMOutput)
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert schema["required"] == ["answer"]
    assert schema["properties"]["answer"]["type"] == "string"
