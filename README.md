# AI-Assisted URL Shortener

A URL shortener service built as an AI-assisted engineering exercise: core APIs,
analytics, and reliability features, developed with disciplined AI-assisted
execution and traceable review decisions (see `REQUIREMENTS_ANALYSIS.md` and
`AI_PROMPTING_FRAMEWORK.md`).

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

## Project status and documentation

- `REQUIREMENTS_ANALYSIS.md` — requirement interpretation, ambiguity
  resolution, assumptions, design decisions and alternatives considered,
  non-functional requirements addressed, and the risk register.
- `ARCHITECTURE.md` — components, tools, execution approach, control
  flow, and key decisions.
- `ENGINEERING_SUMMARY.md` — final plan/rationale, artifacts,
  risks/trade-offs/validation, assumptions, and limitations.
- `AI_PROMPTING_FRAMEWORK.md` — the prompting discipline, grounding
  requirements, guardrails, security practices, and responsible-AI
  principles applied throughout development.

## References

Each reference below grounds a specific design decision — see Section 5
("Design decisions and alternatives considered") of
`REQUIREMENTS_ANALYSIS.md` for how each was applied, including one
deliberate divergence.

- [System Design: URL Shortening Service](https://www.geeksforgeeks.org/system-design/system-design-url-shortening-service/) — schema sizing and collision-handling approach.
- [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) — CSPRNG requirement for unpredictable identifiers.
- [Cloudflare Engineering: Counting things, a lot of different things](https://blog.cloudflare.com/counting-things-a-lot-of-different-things/) — fixed-window vs. sliding-window rate limiting trade-offs.
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) — grounds the operator-configured (not user-supplied) webhook URL decision.
- [FastAPI: Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) — confirms `on_event` is deprecated in favor of `lifespan`.
