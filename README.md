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
