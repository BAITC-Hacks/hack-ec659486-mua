"""Настройки приложения (pydantic-settings).

Источники по приоритету: переменные окружения > backend/.env > <repo>/.env > значения по умолчанию.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

LLMMode = Literal["live", "mock"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Порядок важен: более поздние файлы переопределяют более ранние.
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    app_name: str = "ОргДифф API"
    app_version: str = "0.1.0"

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-luna"
    llm_mode: LLMMode = "mock"

    cors_origins: str = "http://localhost:3000"

    @property
    def llm_live(self) -> bool:
        """Живые вызовы — только при явном LLM_MODE=live."""
        return self.llm_mode == "live"

    @property
    def effective_llm_mode(self) -> LLMMode:
        """Фактический режим равен заявленному.

        Тихой подмены live -> mock нет: иначе демо и проверка эксперта молча идут
        по фикстурам, а /health при этом рапортует mock — расхождение заметят поздно.
        Нет ключа при LLM_MODE=live — приложение не стартует, см. check_startup().
        """
        return self.llm_mode

    def check_startup(self) -> None:
        """Проверки конфигурации до запуска сервера. Бросает RuntimeError с инструкцией."""
        if self.llm_mode == "live" and not self.openai_api_key:
            raise RuntimeError(
                "LLM_MODE=live, но OPENAI_API_KEY пуст. Укажите ключ в .env "
                "или поставьте LLM_MODE=mock — тогда ответы берутся из фикстур "
                "и это видно в /health и в баннере интерфейса."
            )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Кэшированный singleton настроек; в тестах сбрасывается через get_settings.cache_clear()."""
    return Settings()
