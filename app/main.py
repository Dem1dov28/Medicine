from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api import router
from app.storage import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Medical Knowledge Infrastructure (MKI)",
    version=__version__,
    description="v0 — Claims → Evidence → Consensus → Knowledge. See RFC-0000/0001.",
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}
