# AI-Assisted URL Shortener

A URL shortener service built as an AI-assisted engineering exercise: core APIs,
analytics, and reliability features, developed with disciplined AI-assisted
execution and traceable review decisions (see `ASSESSMENT_CONTEXT.md`).

## Stack

Python 3.11+ / FastAPI / SQLAlchemy / SQLite (dev) / pytest

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux

pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload
```

Then visit `http://127.0.0.1:8000/health` — should return `{"status": "ok"}`.

## Test

```bash
pytest -v
```

With coverage:

```bash
pytest --cov=app --cov-report=term-missing
```

## API

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness check; never touches the database; exempt from rate limiting |
| `/shorten` | POST | `{"long_url": "https://..."}` → `201 {"short_code": "...", "long_url": "..."}` |
| `/{short_code}` | GET | `302` redirect to the original URL; `404` if unknown |

## Configuration

All settings are optional env vars (see `app/config.py` for defaults):
`DATABASE_URL`, `SHORT_CODE_LENGTH`, `MAX_COLLISION_RETRIES`,
`MAX_LONG_URL_LENGTH`, `RATE_LIMIT_PER_MINUTE`, `WEBHOOK_URL` (unset by
default — link-creation webhook is opt-in).

## Observability

Every request is logged as a single JSON line (timestamp, level, logger,
message) with a `request_id` — either generated per request or taken from
an incoming `X-Request-ID` header, and always echoed back in the response
headers so a caller can correlate their request with server logs.

## Project status

See `ASSESSMENT_CONTEXT.md` for the running task decomposition, scope
assumptions, and full AI-generated/edited/rejected traceability log.

## References

- [System Design: URL Shortening Service](https://www.geeksforgeeks.org/system-design/system-design-url-shortening-service/) —
  used to cross-check schema sizing (`long_url` ~2048 chars, base62
  `short_code` at 7 chars) and collision-handling approach; see
  "External reference check" in `ASSESSMENT_CONTEXT.md` for the full
  comparison, including a deliberate divergence (SQLite vs. the
  article's NoSQL-at-scale recommendation, which doesn't apply at this
  project's scope).
