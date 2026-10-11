from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    database_url: str

    jwt_secret: SecretStr
    jwt_expire_minutes: int = 60

    llm_api_key: SecretStr

    llm_provider: Literal["groq", "anthropic"] = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    max_tokens: int = 4096

    chunk_size: int = 1000
    chunk_overlap: int = 150

    embedding_provider: Literal["local", "gemini"] = "local"
    retrieval_top_k: int = 4
    max_upload_bytes: int = 10_000_000

    app_env: Literal["local", "staging", "production"] = "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build and cache the settings object.

    Deliberately not called at import time: importing a module must have no
    side effects, so tests and CI can import the app without any credentials.
    Validation is triggered explicitly at application startup (see main.py),
    which keeps fail-fast behaviour where it belongs.
    """
    return Settings()
