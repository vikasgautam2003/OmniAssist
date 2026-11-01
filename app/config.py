from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.jobs.celery_app import DEFAULT_REDIS_URL


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
    max_tool_iterations: int = 5

    redis_url: str = DEFAULT_REDIS_URL

    # JSON locally too would be unreadable; machines read it in production.
    log_json: bool = False
    # Groq's free tier costs nothing, so these default to zero -- but the
    # field exists so token counts can become money the moment a paid
    # provider is configured, which is what v1.0's per-tenant tracking needs.
    cost_per_million_input_tokens: float = 0.0
    cost_per_million_output_tokens: float = 0.0

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
