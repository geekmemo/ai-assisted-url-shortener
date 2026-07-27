# Architecture Overview

## Components

```
app/
  main.py            FastAPI app, routes, middleware wiring, lifespan startup
  config.py           pydantic-settings: single source of truth for all
                       tunable/business-rule constants (never hardcoded
                       elsewhere)
  database.py          SQLAlchemy engine/session factory, get_db() dependency
  models.py            Link (short_code -> long_url mapping) and Click
                       (per-redirect timestamp log) ORM models
  codegen.py            Short-code generation (secrets, not random)
  schemas.py            Pydantic request/response contracts + validation
  rate_limiter.py       In-memory per-IP fixed-window rate limiter
  webhook.py             Outbound link-created notification (opt-in)
  logging_config.py     Structured logging + request-correlation setup

tests/
  conftest.py           Shared TestClient fixture: isolates DB per test,
                        reloads every stateful module (config, database,
                        models, rate_limiter, webhook, main) so no test can
                        silently inherit state from another
  test_*.py             One file per concern (health, models, shorten,
                        redirect, analytics, rate_limit, webhook, logging,
                        startup-timing)
```

## Tools

- **FastAPI** — web framework (routing, validation via Pydantic, dependency
  injection, background tasks, middleware)
- **SQLAlchemy** (ORM + Core) — data model, atomic SQL-level updates
- **SQLite** — storage; zero-install, file-based, adequate for prototype
  scale (see "Key decisions" below for the explicit trade-off against NoSQL)
- **pytest** / **pytest-cov** / **httpx** (TestClient transport) — test
  suite, coverage measurement
- **uvicorn** — ASGI server for local/live runs
- Standard library only for the rest: `secrets` (code generation),
  `contextvars` (request correlation), `threading.Lock` (rate limiter),
  `logging` (structured output)

## Execution approach

Every task in this project followed the same loop, driven by AI-assisted
generation with explicit human review at each step:

1. **Decompose** the task with dependencies and acceptance criteria,
   documented before implementation started
2. **Generate** the implementation with AI assistance
3. **Review** — accept as-is, edit, or reject each generated piece, with a
   stated rationale (never a blanket accept)
4. **Test** — write/run tests proving the acceptance criteria, not just
   that the happy path works
5. **Boot-verify** — run the real app with a live server and real HTTP
   calls (`curl`/independent processes), not just in-process TestClient,
   for every task
6. **Log** the decision in a running traceability record (accept/edit/
   reject with rationale for every AI-generated piece)
7. **Commit and push** each task as its own commit

This loop is why the process included entries like "rejected AI's first
draft" and "found a real bug" rather than only "accepted as generated" —
the review step was substantive, not procedural. See
`AI_PROMPTING_FRAMEWORK.md` for the full grounding/guardrail discipline
this loop was run under.

## Control flow

**`POST /shorten`:**
```
Request -> RateLimitMiddleware -> RequestLoggingMiddleware -> validate
(Pydantic: real URL parsing + max-length check) -> generate short_code
(secrets, base62, 7 chars) -> insert Link (retry on unique-constraint
collision, up to max_collision_retries) -> commit -> schedule webhook
as BackgroundTask (fires after response is sent) -> return 201
```

**`GET /{short_code}`:**
```
Request -> RateLimitMiddleware -> RequestLoggingMiddleware -> look up
Link by short_code (404 if missing) -> atomic SQL increment of
click_count + insert Click row (commit failures logged, never block
the redirect) -> return 302 to long_url
```

Both middlewares wrap every route except `/health`, which is exempt from
rate limiting (but still logged).

## Key decisions

(Full rationale for each, including alternatives considered, is in
`REQUIREMENTS_ANALYSIS.md` Sections 5-6 — this is a summary, not a
replacement.)

- **SQLite over NoSQL**, despite a standard system-design reference
  recommending NoSQL at 30M-user scale — that recommendation is scale-
  driven, not correctness-driven, and doesn't apply to this project's
  scope. See Section 5 of `REQUIREMENTS_ANALYSIS.md`.
- **Atomic SQL-level increments** (`UPDATE ... SET x = x + 1`) instead of
  Python read-modify-write, to avoid lost updates under concurrent
  redirects — verified with both an in-process 25-thread test and a live
  20-process concurrent `curl` test.
- **Failures in side-effects (click logging, webhook delivery) never
  block the primary response** — a broken analytics write or an
  unreachable webhook must not turn into a broken redirect or a failed
  shorten. This pattern repeats across Tasks 5, the brownfield webhook,
  and the ambiguous-scenario logging work, and is now itself observable
  via structured logs instead of silently swallowed.
- **`secrets`, not `random`, for short-code generation** — predictable
  codes are a real enumeration/guessing risk for a public redirect
  service.
- **Rate limiting is in-memory, single-process** — a deliberate scope
  limit for a prototype; documented as not viable across multiple
  instances without a shared backend (e.g. Redis) if this were ever
  horizontally scaled.
