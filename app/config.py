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

    # Tuning knobs for the retrieval pipeline, not constants. 1000 characters
    # is roughly 250 tokens -- well inside the 512-token limit of the local
    # embedding model -- and small enough that a retrieved chunk is a focused
    # passage rather than a page. 150 is about 15% overlap, enough to carry a
    # sentence across a boundary.
    chunk_size: int = 1000
    chunk_overlap: int = 150

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
