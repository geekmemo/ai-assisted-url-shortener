from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, engine
from app.models import Link  # noqa: F401 — import registers Link with Base.metadata


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="URL Shortener", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
