from app.clients.base import LLMClient, LLMError
from app.config import settings


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "groq":
        from app.clients.groq_client import GroqClient

        return GroqClient(
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
            max_tokens=settings.max_tokens,
        )

    raise LLMError(f"Unsupported provider: {settings.llm_provider}")