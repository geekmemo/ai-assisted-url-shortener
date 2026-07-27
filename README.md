# AI-Assisted URL Shortener

A URL shortener service built as an AI-assisted engineering exercise: core APIs,
analytics, and reliability features, developed with disciplined AI-assisted
execution and traceable review decisions (see `REQUIREMENTS_ANALYSIS.md` and
`AI_PROMPTING_FRAMEWORK.md`).

## Stack

Python 3.11+ / FastAPI / SQLAlchemy / SQLite (dev) / pytest

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

(`python -m uvicorn ...` rather than the bare `uvicorn` command — see
Troubleshooting below for why this matters on Windows.)

Then visit `http://127.0.0.1:8000/health` — should return `{"status": "ok"}`.

## Test

```bash
python -m pytest -v
```

With coverage:

```bash
python -m pytest --cov=app --cov-report=term-missing
```

## Troubleshooting

**`python : The term 'python' is not recognized` / opens the Microsoft
Store** — Windows ships a fake `python` command that only exists to
prompt a Store install. Install Python 3.11+ from
[python.org](https://www.python.org/downloads/) or via
`winget install Python.Python.3.12`, then **fully close and reopen your
terminal** (a new tab is not enough — PATH is only refreshed by a new
terminal process). If it's still not found afterward, call the
interpreter by its full install path directly, e.g.
`C:\Users\<you>\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv`.

**`Permission denied: '...\.venv\Scripts\python.exe'` when creating a
venv** — a `.venv` already exists and is *active in the current shell*
(check for `(.venv)` in your prompt); Windows locks a running
interpreter's executable, so it can't be overwritten in place. Either
just use the existing venv (skip straight to `pip install` / running
tests), or `deactivate` first, delete the `.venv` folder, and recreate it.

**Everything fails and nothing looks right** — check you're actually in
the project directory: run `pwd` (or look at your prompt) and confirm
it ends in `AIAssistedSW`, and that `ls` shows `app/`, `tests/`,
`requirements.txt`. Commands run from the wrong directory fail in
confusing, unrelated-looking ways.

**`uvicorn.exe : ... blocked by an Application Control policy` /
mentions "Smart App Control"** — Windows Smart App Control blocks the
standalone `uvicorn.exe` launcher as an unrecognized executable. Run it
through the Python interpreter instead: `python -m uvicorn app.main:app
--reload` (this is why the Run section above uses that form directly).

**Browser shows `ERR_CONNECTION_REFUSED` right after starting the
server** — there's a short window between running the start command
and the server actually listening; wait a couple seconds and reload.
If it persists, verify the server is really up before blaming the
browser: `curl.exe http://127.0.0.1:8000/health` from a second
terminal — if that also fails, the server isn't running (check the
terminal running `uvicorn` for a startup error); if `curl.exe`
succeeds but the browser doesn't, it's browser/proxy/firewall-specific,
not the app.

**In PowerShell, `curl -i ...` prompts for a "Uri" and then fails with
`Cannot find drive. A drive with the name 'http' does not exist`** —
PowerShell aliases the bare `curl` command to `Invoke-WebRequest`,
which does not understand curl's flags (`-i` in particular) and misparses
the URL as a result. Use `curl.exe` (with the extension) everywhere in
this README instead of `curl` — that runs the real curl binary, not the
PowerShell alias.

## Manual testing walkthrough

With the server running (`python -m uvicorn app.main:app --reload`),
these are the things worth checking by hand and what each should show.
All examples use `curl`; a browser works fine for the two `GET`
requests, but `POST` needs `curl`, VS Code's REST Client, Postman, or
similar.

**1. Health check** — should always return `200` instantly, with no
database access:

```bash
curl.exe -i http://127.0.0.1:8000/health
```

Expected:
```
HTTP/1.1 200 OK
{"status":"ok"}
```

**2. Create a short link** — the core feature:

```bash
curl.exe -i -X POST http://127.0.0.1:8000/shorten \
  -H "Content-Type: application/json" \
  -d "{\"long_url\": \"https://example.com/some/very/long/path\"}"
```

Expected: `201 Created` with a generated 7-character `short_code`:
```
HTTP/1.1 201 Created
{"short_code":"aZ3kQ1x","long_url":"https://example.com/some/very/long/path"}
```

Copy the `short_code` from the response for the next steps.

**3. Follow the redirect** — replace `aZ3kQ1x` with the code you got back:

```bash
curl.exe -i http://127.0.0.1:8000/aZ3kQ1x
```

Expected: `302 Found` with a `Location` header pointing at the original URL:
```
HTTP/1.1 302 Found
location: https://example.com/some/very/long/path
```

(Or just paste `http://127.0.0.1:8000/aZ3kQ1x` into a browser — it
should navigate straight to `example.com`.)

**4. Unknown code returns 404**:

```bash
curl.exe -i http://127.0.0.1:8000/doesnotexist
```
Expected: `HTTP/1.1 404 Not Found`

**5. Invalid URL is rejected with 422**:

```bash
curl.exe -i -X POST http://127.0.0.1:8000/shorten \
  -H "Content-Type: application/json" \
  -d "{\"long_url\": \"not-a-url\"}"
```
Expected: `HTTP/1.1 422 Unprocessable Entity` with a validation error body.

**6. Rate limiting** — restart the server with a low threshold to see
it trip:

```bash
$env:RATE_LIMIT_PER_MINUTE=3   # PowerShell; use `export` on macOS/Linux
python -m uvicorn app.main:app --reload
```

Then hit any non-`/health` endpoint 4 times in a row (e.g. re-run step
4 four times) — the 4th should return `HTTP/1.1 429 Too Many Requests`.
`/health` is exempt and will keep returning `200` regardless.

**7. Request correlation** — every response carries an `X-Request-ID`
header; check it's present and that the same ID shows up in the
server's terminal log line for that request:

```bash
curl.exe -i http://127.0.0.1:8000/health
```
Look for `x-request-id: <uuid>` in the response, and a matching
`request_id=<uuid>` in the JSON log line printed in the terminal
running `uvicorn`.

**8. Automated suite** — the fast way to check everything at once
rather than clicking through the above by hand:

```bash
python -m pytest -v
```
Expected: `30 passed`.

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
