from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.routes.chat import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Validate configuration before the server accepts any traffic.

    Config is loaded lazily so imports stay side-effect free; this is where
    fail-fast is re-established. A missing or invalid value stops the process
    from starting rather than failing on the first user request.
    """
    get_settings()
    yield


app = FastAPI(title="OmniAssist", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
