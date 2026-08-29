from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    llm_api_key: SecretStr

    llm_provider: Literal["groq", "anthropic"] = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    max_tokens: int = 4096
    app_env: Literal["local", "staging", "production"] = "local"


settings = Settings()
