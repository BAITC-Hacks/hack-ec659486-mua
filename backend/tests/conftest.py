"""Фикстуры pytest: приложение принудительно в mock-режиме, без ключа OpenAI."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    # Переменные окружения имеют приоритет над .env, поэтому даже с локальным
    # LLM_MODE=live тесты идут в mock-режиме и не тратят токены.
    monkeypatch.setenv("LLM_MODE", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()
