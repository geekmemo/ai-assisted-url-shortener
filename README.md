# AI-Assisted URL Shortener

[![CI](https://github.com/geekmemo/ai-assisted-url-shortener/actions/workflows/ci.yml/badge.svg)](https://github.com/geekmemo/ai-assisted-url-shortener/actions/workflows/ci.yml)

A URL shortener service: submit a long URL, get back a short code that
redirects to it, with click analytics and reliability features built
in. Built as an AI-assisted engineering exercise, with disciplined
AI-assisted execution and traceable review decisions (see
`REQUIREMENTS_ANALYSIS.md` and `AI_PROMPTING_FRAMEWORK.md`).

## Features

- **Short link creation** — collision-safe code generation (`secrets`,
  base62, 7 characters)
- **Redirect** — `302` to the original URL, `404` if the code doesn't exist
- **Click analytics** — an atomic running counter plus a timestamped
  event log per link, correct under concurrent traffic
- **Per-IP rate limiting** — configurable threshold, `429` past it,
  `/health` exempt
- **Opt-in webhook** — notifies an external endpoint when a link is
  created, without adding latency to the request that created it
- **Structured logging** — every request logged as JSON with a
  correlation ID, echoed back in an `X-Request-ID` response header
- **Auto-generated API docs** — FastAPI serves a full OpenAPI schema
  from the code itself; no separate spec to keep in sync

## API

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness check; never touches the database; exempt from rate limiting |
| `/shorten` | POST | `{"long_url": "https://..."}` → `201 {"short_code": "...", "long_url": "..."}` |
| `/{short_code}` | GET | `302` redirect to the original URL; `404` if unknown |

With the server running, visit `http://127.0.0.1:8000/docs` for
interactive Swagger UI, or `http://127.0.0.1:8000/openapi.json` for the
raw schema.

## Documentation

- `ARCHITECTURE.md` — components, tools, execution approach, control flow, key decisions
- `REQUIREMENTS_ANALYSIS.md` — requirement interpretation, assumptions, design decisions and alternatives considered, risk register
- `ENGINEERING_SUMMARY.md` — plan/rationale, artifacts, testing approach, risks/trade-offs, assumptions, limitations, and quick-reference tables mapping the assignment's scope and evaluation criteria to evidence
- `AI_PROMPTING_FRAMEWORK.md` — prompting discipline, grounding requirements, guardrails, security practices, responsible-AI principles
- `TRACEABILITY.md` — every AI-generated piece of this project with its accept/edit/reject decision and rationale

## Setup

Requires Python 3.11+. From the project root:

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS/Linux

pip install -r requirements.txt
```

## Run

```bash
python -m uvicorn app.main:app --reload
```

Then visit `http://127.0.0.1:8000/health` — should return `{"status": "ok"}`.

## Test

```bash
python -m pytest -v
```

With coverage:

```bash
python -m pytest --cov=app --cov-report=term-missing
```

## Quality gates

All of these run automatically on every push via
`.github/workflows/ci.yml` (see the CI badge above), not just checked
manually once:

```bash
python -m ruff check .                    # lint / static analysis
python -m bandit -r app/                  # security static analysis
python -m pip_audit -r requirements.txt   # dependency vulnerability scan
python -m pytest --cov=app --cov-fail-under=100   # tests, coverage enforced
```

`B008` (flake8-bugbear's "function call in default argument" rule) is
deliberately disabled in `pyproject.toml` — it's a false positive for
FastAPI's `Depends(...)` dependency-injection pattern, which relies on
exactly that construct by design.

**Known gap**: static type checking (`mypy`) was attempted but is
blocked on this development machine by Windows Smart App Control.
Deliberately not added to CI unverified — see `REQUIREMENTS_ANALYSIS.md`
§4.4 for the full note.

## Configuration

All settings are optional env vars (see `app/config.py` for defaults):
`DATABASE_URL`, `SHORT_CODE_LENGTH`, `MAX_COLLISION_RETRIES`,
`MAX_LONG_URL_LENGTH`, `RATE_LIMIT_PER_MINUTE`, `WEBHOOK_URL` (unset by
default — link-creation webhook is opt-in).

By default this creates `url_shortener.db` in the project directory.
Data persists there across server restarts — `create_all()` only
creates missing tables on startup, it never wipes existing ones. The
file is deliberately excluded from version control (`.gitignore`), the
same way any real project excludes its local dev database — that's
about not committing runtime state as if it were source code, not a
statement that the app itself doesn't persist data.

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

---

## Appendix: manual testing walkthrough

With the server running, these are the things worth checking by hand
and what each should show. Examples use `curl`; a browser works fine
for the two `GET` requests, but `POST` needs `curl`, VS Code's REST
Client, Postman, or similar. This is a convenience checklist —
`python -m pytest -v` (32 tests) is the actual verification.

**1. Health check:**
```bash
curl.exe -i http://127.0.0.1:8000/health
```
Expected: `200 {"status":"ok"}`

**2. Create a short link:**
```bash
curl.exe -i -X POST http://127.0.0.1:8000/shorten \
  -H "Content-Type: application/json" \
  -d "{\"long_url\": \"https://example.com/some/very/long/path\"}"
```
Expected: `201 {"short_code":"aZ3kQ1x","long_url":"https://example.com/some/very/long/path"}` — copy the `short_code` for the next steps.

**3. Follow the redirect** (use your actual code):
```bash
curl.exe -i http://127.0.0.1:8000/aZ3kQ1x
```
Expected: `302 Found` with a `location` header pointing at the original URL — or paste the same URL into a browser.

**4. Unknown code returns 404:**
```bash
curl.exe -i http://127.0.0.1:8000/doesnotexist
```

**5. Invalid URL is rejected with 422:**
```bash
curl.exe -i -X POST http://127.0.0.1:8000/shorten \
  -H "Content-Type: application/json" \
  -d "{\"long_url\": \"not-a-url\"}"
```

**6. Rate limiting** — restart with a low threshold, then hit any non-`/health` endpoint 4 times in a row:
```bash
$env:RATE_LIMIT_PER_MINUTE=3   # PowerShell; use `export` on macOS/Linux
python -m uvicorn app.main:app --reload
```
The 4th request should return `429`; `/health` keeps returning `200` regardless.

**7. Request correlation** — check the `x-request-id` response header matches the `request_id=` value in the server's terminal log line for that same request.

## Appendix: troubleshooting (Windows dev environment)

Issues actually hit while setting this project up, kept here in case
they recur:

- **`python` not recognized / opens the Microsoft Store** — Windows'
  fake `python` stub. Install from
  [python.org](https://www.python.org/downloads/) or
  `winget install Python.Python.3.12`, then fully close and reopen your
  terminal (PATH only refreshes on a new terminal process).
- **`Permission denied: ...\.venv\Scripts\python.exe` creating a venv**
  — a `.venv` is already active in that shell (check for `(.venv)` in
  the prompt); Windows locks a running interpreter's executable. Use
  the existing venv, or `deactivate` first and recreate it.
- **Nothing works and errors look unrelated** — confirm you're actually
  in the project directory (`pwd`; `ls` should show `app/`, `tests/`,
  `requirements.txt`).
- **`uvicorn.exe` blocked by "Smart App Control"** — run it through the
  interpreter instead: `python -m uvicorn app.main:app --reload`.
- **Browser shows `ERR_CONNECTION_REFUSED` right after starting** —
  timing; wait a couple seconds and reload. Verify with
  `curl.exe http://127.0.0.1:8000/health` from a second terminal before
  assuming the server itself is broken.
- **PowerShell: `curl -i ...` fails with `Cannot find drive 'http'`** —
  PowerShell aliases bare `curl` to `Invoke-WebRequest`, which
  misparses curl flags. Use `curl.exe` (with the extension) instead.
