import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app.codegen import generate_short_code
from app.config import settings
from app.database import Base, engine, get_db
from app.logging_config import configure_logging, request_id_var
from app.models import Click, Link
from app.rate_limiter import rate_limiter
from app.schemas import ShortenRequest, ShortenResponse
from app.webhook import send_link_created_webhook

configure_logging()
logger = logging.getLogger(__name__)

# Exempt from rate limiting: a monitored liveness check shouldn't be able to
# trip 429s and get flagged as "unhealthy" by whatever polls it.
_RATE_LIMIT_EXEMPT_PATHS = {"/health"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in _RATE_LIMIT_EXEMPT_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.allow(client_ip):
            return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": "Rate limit exceeded"})

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        start = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            logger.info(
                f"request_id={request_id} {request.method} {request.url.path} "
                f"-> {response.status_code} ({duration_ms}ms)"
            )
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="URL Shortener", lifespan=lifespan)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestLoggingMiddleware)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED)
def shorten(payload: ShortenRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
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
        # Runs after the response is sent — a slow or unreachable webhook
        # endpoint can never add latency to, or fail, the caller's request.
        # request_id is captured now and passed explicitly rather than read
        # from the contextvar inside the background task, since it's unclear
        # whether that background task runs before or after
        # RequestLoggingMiddleware resets the contextvar.
        background_tasks.add_task(
            send_link_created_webhook, link.short_code, link.long_url, request_id_var.get()
        )
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

    long_url = link.long_url

    # Atomic SQL-level increment (SET click_count = click_count + 1), not a
    # Python read-modify-write, so concurrent redirects can't lose updates to
    # a stale in-memory value. Recording failures never block the redirect
    # itself — a broken counter shouldn't turn into a broken link.
    try:
        db.query(Link).filter_by(id=link.id).update({Link.click_count: Link.click_count + 1})
        db.add(Click(link_id=link.id))
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.warning(
            f"request_id={request_id_var.get()} click recording failed for short_code={short_code}: {exc}"
        )

    return RedirectResponse(url=long_url, status_code=status.HTTP_302_FOUND)
