from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.observability.logging import configure, get_logger
from app.observability.middleware import RequestLogging
from app.routes.artifacts import router as artifacts_router
from app.routes.auth import router as auth_router
from app.routes.chat import router
from app.routes.documents import router as documents_router
from app.routes.organisations import router as organisations_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration before the server accepts any traffic.

    Config is loaded lazily so imports stay side-effect free; this is where
    fail-fast is re-established. A missing or invalid value stops the process
    from starting rather than failing on the first user request.
    """
    settings = get_settings()
    configure(json_output=settings.log_json)
    get_logger("app").info("startup", env=settings.app_env, model=settings.llm_model)
    yield


app = FastAPI(title="OmniAssist", version="0.3.0", lifespan=lifespan)
app.add_middleware(RequestLogging)
app.include_router(auth_router)
app.include_router(router)
app.include_router(documents_router)
app.include_router(artifacts_router)
app.include_router(organisations_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
