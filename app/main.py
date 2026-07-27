from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.codegen import generate_short_code
from app.config import settings
from app.database import Base, engine, get_db
from app.models import Link
from app.schemas import ShortenRequest, ShortenResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="URL Shortener", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED)
def shorten(payload: ShortenRequest, db: Session = Depends(get_db)):
    long_url = str(payload.long_url)

    for _ in range(settings.max_collision_retries):
        short_code = generate_short_code(settings.short_code_length)
        link = Link(short_code=short_code, long_url=long_url)
        db.add(link)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(link)
        return ShortenResponse(short_code=link.short_code, long_url=link.long_url)

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Unable to generate a unique short code, please retry",
    )


# Registered last: this single-segment catch-all would shadow /health and
# /shorten (GET) if declared above them, since FastAPI matches path routes
# in registration order.
@app.get("/{short_code}")
def redirect_to_long_url(short_code: str, db: Session = Depends(get_db)):
    link = db.query(Link).filter_by(short_code=short_code).first()
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="short_code not found")
    return RedirectResponse(url=link.long_url, status_code=status.HTTP_302_FOUND)
