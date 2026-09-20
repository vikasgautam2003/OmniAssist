from fastapi import FastAPI

from app.routes.chat import router

app = FastAPI(title="OmniAssist", version="0.1.0")
app.include_router(router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
