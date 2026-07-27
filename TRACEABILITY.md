# AI-Assisted Execution Traceability

This is the running record of every AI-generated piece of this project,
with an explicit accept/edit/reject decision and rationale for each —
per the assignment's requirement to "maintain traceability
(generated/edited/rejected with rationale)." Nothing here is
reconstructed after the fact; it was kept as work happened.

## Greenfield (Tasks 1-7)

Task decomposition, agreed before implementation started:

| # | Task | Depends on | Acceptance criteria |
|---|---|---|---|
| 1 | Project scaffold (FastAPI app, config, DB setup, health check) | — | App boots; `GET /health` returns 200 |
| 2 | Data model: `Link(id, short_code, long_url, created_at)` | 1 | `create_all()` runs; unique constraint on `short_code` |
| 3 | `POST /shorten` — create short URL, collision-safe code generation | 2 | Returns 201 + short_code; collision retry logic tested |
| 4 | `GET /{short_code}` — redirect | 2 | 302 to long_url; 404 on unknown code |
| 5 | Analytics: click counter + timestamp log per redirect | 4 | Click count increments atomically under concurrent hits |
| 6 | Reliability: rate limiting middleware | 3, 4 | 429 past threshold; per-IP, configurable |
| 7 | Test suite: unit + integration | 3, 4, 5, 6 | High coverage on core logic; concurrency test for collisions |

Per-decision log for each task:

| Ref | Prompt intent | AI output summary | Review | Decision |
|---|---|---|---|---|
| 1a | Generate FastAPI settings class (pydantic-settings) | Standard `BaseSettings` subclass with `database_url`, `short_code_length`, `max_collision_retries` | Initially over-generated a `rate_limit_per_minute` field belonging to a later task — removed to avoid speculative config before that task exists | Edited |
| 1b | Generate SQLAlchemy engine/session boilerplate | Standard session-per-request pattern with conditional `check_same_thread` for SQLite | Correct as generated, low risk | Accepted as-is |
| 1c | Generate `main.py` with table creation + health check | Used FastAPI's `lifespan` context manager (rather than `@app.on_event("startup")`) to run `create_all()` at startup, not import time | Preferred over `on_event` since it's deprecated upstream; confirmed against FastAPI's own docs | Accepted (judgment call, later externally verified) |
| 1d | Generate smoke test for `/health` using `TestClient` | Basic 200 + JSON body assertion | Correct as generated | Accepted as-is |
| 1e | Boot verification | Ran a real `uvicorn` server (not just in-process `TestClient`) and hit `/health` over HTTP | N/A — manual verification, no code to review | Verified live over real HTTP |
| 1f | Regression test for `create_all()` import-vs-startup timing | Two tests using `importlib.reload` + env var override to force fresh module instantiation, asserting the DB file doesn't exist after import but does after startup | Closed this test-debt item immediately rather than deferring it | Accepted |
| 1g | Pin `requirements.txt` to exact installed versions | — | Reinstalled from the pinned file, full suite re-run | Accepted |
| 2a | Generate `Link` SQLAlchemy model | Modern `Mapped`/`mapped_column` style; `short_code unique=True, index=True`; timezone-aware `created_at` default | Timezone-aware default is deliberate — avoids naive-datetime ambiguity | Accepted |
| 2b | Wire `Link` into `main.py` so `create_all()` registers the table | Plain import | Added an inline comment explaining *why* the import matters (SQLAlchemy only registers models it has imported before `create_all()` runs) — easy to silently "clean up" otherwise | Accepted with comment added |
| 2c | Tests for table creation + unique constraint | Happy-path insert/read, and duplicate `short_code` expected to raise `IntegrityError` | Correct as generated | Accepted as-is |
| 2d | Boot verification | Live `uvicorn` after adding the model, confirming `create_all()` still succeeds | N/A | Verified |
| 3a | Generate short-code generator | AI's first draft used `random.choices()` | Rejected — `random` is not cryptographically secure; predictable codes are a real guessing/enumeration risk. Replaced with `secrets.choice()` | Edited |
| 3b | Generate request/response schemas | Used Pydantic's `HttpUrl` for real URL validation, not a bare `str` | Closes a real gap: SQLite doesn't enforce column length/format at the DB level | Accepted |
| 3c | Schema hardcoded a max-length constant as a local module constant | — | Rejected placement — violated the convention that config lives in one place; moved to settings, referenced from both the validator and the DB column | Edited |
| 3d | Generate `POST /shorten` with collision-retry loop | Loops up to a configurable cap, catches `IntegrityError`, returns `503` if exhausted | Matches the documented collision strategy | Accepted as-is |
| 3e | Tests: happy path, invalid URL, oversized URL, collision retry (forced via monkeypatch), retries-exhausted | All passed on first run | The collision test specifically forces two identical generated codes to prove the retry loop executes, not just that the happy path works | Accepted as-is |
| 3f | Boot verification | Live `uvicorn` + `curl`: valid URL → `201`; invalid → `422` | N/A | Verified over real HTTP |
| 4a | Generate redirect endpoint | AI's first draft's route placement wasn't reviewed for ordering | Rejected the default placement — a bare path-parameter route matches *any* single-segment path, so it would shadow `/health` if registered first. Required registering it last, with a regression test | Edited |
| 4b | Use `RedirectResponse` (302) + `HTTPException` (404) | Correct as generated | — | Accepted as-is |
| 4c | Tests: 302 + correct location header, 404 for unknown code, explicit non-shadowing check | All passed | The non-shadowing test directly guards the 4a decision | Accepted as-is |
| 4d | Boot verification | Live full round trip: shorten → redirect → correct URL; unknown code → 404 | N/A | Verified |
| 5a | Add click counter + event log | AI's first draft incremented the counter in Python (`link.click_count += 1`) before writing back | Rejected — a Python read-modify-write is a classic lost-update race under concurrency. Replaced with a single atomic SQL `UPDATE ... SET x = x + 1` | Edited |
| 5b | Add a SQLite busy `timeout` | Not present in the original scaffold | Added deliberately — without it, concurrent writers can hit "database is locked" immediately instead of waiting briefly; verified necessary via a concurrent test | Edited (engineer addition) |
| 5c | Decide whether a failed analytics write should block the redirect | Engineer decision, not AI-suggested | Wrapped in `try/except` with rollback so a broken analytics write can never turn into a broken redirect | Accepted |
| 5d | Concurrency test: many threads hitting the same link, assert exact count | Passed on first run; re-ran standalone 5x to rule out flakiness | This is the one acceptance criterion that's actually hard to get right, so it got the most scrutiny | Accepted |
| 5e | Boot verification | Real concurrent OS-level processes (not just in-process threads) against a live server, exact count confirmed | N/A | Verified |
| 6a | Generate a fixed-window rate limiter + middleware | Correct as generated, including the lock around shared state | Appropriate for single-process scope; the algorithm's known trade-off (burst at window-reset boundaries) was later externally confirmed and documented, not discovered by accident | Accepted, limitation documented |
| 6b | Decide whether `/health` should be rate-limited | Engineer decision | A liveness check tripping 429s would get falsely flagged unhealthy by whatever polls it — excluded explicitly | Accepted |
| 6c | Decide IP source for the limiter | Engineer decision | Deliberately did not trust a client-supplied header (spoofable); used the actual transport-level connection IP | Accepted, risk documented |
| 6d | Found a real test-isolation bug | A test file's fixture didn't reload the rate-limiter module, inheriting leftover state from an alphabetically-earlier test file and failing unexpectedly | Root cause: six test files had each hand-rolled a slightly different version of the same module-reload pattern, and one omitted a step. Consolidated into one shared fixture | Edited: extracted a shared test fixture |
| 6e | Rate-limit tests: threshold logic, configurability, health exemption | All passed; re-ran the full suite 3x plus once in reversed file order to confirm the isolation fix held regardless of run order | — | Accepted as-is |
| 6f | Boot verification | Live server, low threshold: health unaffected, other paths correctly capped and returning 429 | N/A | Verified |
| 7a | Measure coverage | Baseline below 100%, two lines uncovered | Investigated both gaps rather than padding the metric | Found real gaps, not noise |
| 7b | Investigate one coverage gap | Discovered an existing test was passing for the *wrong reason* — an upstream library's own validation was firing before this project's own check ever ran | Rejected the existing test as insufficient; added a second test targeting the exact narrow range only this project's own validator would catch | Edited: split into two tests |
| 7c | Investigate the other coverage gap | The gap was in the exact "a broken side-effect must never break the primary response" code path — asserted in prose but never actually exercised by a test | Added a test that forces the failure and asserts the primary response still succeeds | Added — arguably the single most important test in the suite |
| 7d | Re-verify after closing both gaps | 100% coverage, full suite green | Also ran a from-scratch clean-room reinstall to confirm nothing depended on leftover state | Verified: stable, reproducible |
| 7e | Pin the coverage tool's version | — | Consistent with the earlier pinning decision | Accepted |
| 7f | Add static analysis/linting (`ruff`) — this had never actually been run | 14 findings: 2 false positives (a flagged pattern that's actually FastAPI's documented, required dependency-injection idiom), 5 import-ordering issues, 7 genuinely unused test variables | The false positive was disabled with a documented reason in config, not silently ignored; the rest were real and fixed | Edited: config added, imports reordered, unused variables renamed |
| 7g | Researched current industry quality-gate practice for AI-generated code, then closed the gaps found: added `bandit` (security static analysis) and `pip-audit` (dependency vulnerability scanning) | Both ran clean on first try — no findings | Attempted `mypy` (type checking) twice (standard install, forced source install); both blocked by this machine's Smart App Control policy. Deliberately not added to CI unverified, since an unverified gate risks a broken pipeline on first run — worse than the gap itself. Documented honestly as a known limitation rather than silently dropped | Added: `bandit`, `pip-audit`; `mypy` recorded as a genuine gap, not hidden |
| 7h | Add `.github/workflows/ci.yml` running lint + security scan + dependency scan + tests (100% coverage enforced) on every push | Correct as generated; runs on a clean Linux CI environment, independent of this Windows dev machine's local quirks | Verified the exact command sequence locally before pushing, so the first real CI run wasn't a guess | Accepted |

## Brownfield: webhook on link creation

**Codebase reasoning — impacted modules, APIs, and data flow**, worked
through before any code was written, since this is an enhancement to
already-shipped code, not a from-scratch build:

- `app/config.py` — one new optional setting, `webhook_url` (default
  `None`, opt-in). Not configuring it must leave all existing behavior
  untouched.
- `app/main.py`'s `POST /shorten` (the existing endpoint from Task 3) —
  its request/response contract is unchanged; the only new behavior is
  a side effect fired *after* the database commit succeeds. No new
  public API surface is introduced.
- New module `app/webhook.py` — kept isolated so the HTTP-dispatch
  concern doesn't entangle with the core shorten logic, and so it's
  separately mockable in tests without touching the network.
- Data flow: `POST /shorten` → `Link` persisted (unchanged) → response
  returned to the caller (unchanged) → webhook POST fired as a
  background task *after* the response is already sent, so a slow or
  unreachable webhook endpoint can never add latency to, or block, the
  caller's request.

Task decomposition:

| # | Task | Depends on | Acceptance criteria |
|---|---|---|---|
| B1 | Add `webhook_url` config (optional, disabled by default) | — | Existing behavior unchanged when unset |
| B2 | Webhook dispatch: fire-and-forget POST with short_code/long_url payload | B1 | Only called when `webhook_url` is set; failures never raise |
| B3 | Wire into `POST /shorten` via a background task | B2, Task 3 | Webhook does not block or slow the `/shorten` response |
| B4 | Tests: called-when-configured, not-called-when-unset, `/shorten` still returns 201 if the webhook call fails | B3 | All pass; response latency unaffected by webhook failure |

Per-decision log:

| Ref | Prompt intent | AI output summary | Review | Decision |
|---|---|---|---|---|
| B1 | Add an optional webhook-URL setting, disabled by default | Correct as generated | — | Accepted as-is |
| B2 | Generate the webhook dispatch function | No-ops if unset; wraps the HTTP call in a try/except | Same resilience pattern as 5c: a broken external system must never break this service's own core function | Accepted |
| B3 | Wire into the create endpoint via a background task | AI correctly used a background task (runs after the response is sent) rather than an inline synchronous call | This is the architecturally important choice: an inline call would let a slow/unreachable endpoint add latency to, or fail, the caller's request | Accepted |
| B4 | Found the same class of bug as 6d | The webhook module reads settings at import time, so it needed the same fixture treatment or it would leak stale state across tests | Added to the shared fixture's reload list before it caused an actual failure, not after | Edited |
| B5 | Tests: not-called-when-unset, called-with-correct-payload, create-still-succeeds-if-webhook-fails | All passed | — | Accepted as-is |
| B6 | Boot verification | A second, real, independent HTTP server (not mocked) as the receiver, alongside a live instance pointed at it | N/A | Verified: correct payload received, primary response unaffected by the webhook's outcome |

## Ambiguous requirement: "make it enterprise-ready"

Task decomposition, agreed after the ambiguity was resolved to a
concrete observability scope (see `REQUIREMENTS_ANALYSIS.md` for the
interpretation and out-of-scope items):

| # | Task | Depends on | Acceptance criteria |
|---|---|---|---|
| A1 | Structured logging config | — | Logs emit a consistent format with timestamp/level/logger/message |
| A2 | Per-request correlation ID, surfaced as an `X-Request-ID` response header | A1 | Every response carries a request ID; a caller-supplied one is honored if present |
| A3 | Request-completion logging middleware | A1, A2 | Every request logs method/path/status/duration with its request ID |
| A4 | Surface the two previously-silent failure paths as logged warnings, without changing their resilience behavior | A1 | Failures are visible in logs; responses are unaffected |
| A5 | Tests for A3 and A4 | A1-A4 | All pass; coverage maintained |

Per-decision log:

| Ref | Prompt intent | AI output summary | Review | Decision |
|---|---|---|---|---|
| A1 | Structured logging config | AI's first instinct used a logging Filter to inject the request ID | Rejected — filters attached to one logger/handler don't reliably propagate to records seen by other handlers (notably the test framework's own log capture), which caused real, non-obvious test failures. Replaced with explicit interpolation into each message | Edited |
| A2/A3 | Request-logging middleware: correlation ID, method/path/status/duration | Correct as generated | Empirically confirmed (not assumed from memory) that this middleware wraps outside the rate limiter and correctly logs even rejected requests | Accepted |
| A4a | Surface one previously-silent failure as a logged warning | Correct as generated | Behavior unchanged, only visibility added | Accepted |
| A4b | Surface the other previously-silent failure, using the correlation ID | AI's first draft read the correlation ID from within a background task | Rejected — it wasn't guaranteed whether that background task runs before or after the middleware resets the ID's scope. Changed to capture the ID in the request handler and pass it explicitly | Edited |
| A5 | Tests for the logging and both surfaced failures | One test failed on first run: it reloaded modules directly in the test body rather than via a fixture, so the test framework's own log capture was already attached *before* the reload wiped it out | Root cause: same class of fixture-vs-manual-reload ordering issue as before. Fixed by moving the reload into a fixture | Edited |
| A6 | Boot verification | Live server: confirmed the correlation-ID response header and structured log lines for every route | N/A | Verified over real HTTP |

## Post-hoc external reference grounding

Several decisions made from engineering judgment alone were, after the
fact, cross-checked against credible external sources — same discipline
as the schema-sizing check done during Task 2, applied retroactively
wherever a decision had been asserted without independent verification:

- `lifespan` over `on_event` (1c) — confirmed against FastAPI's own documentation
- `secrets` over `random` (3a) — grounded against OWASP's session-management guidance on cryptographically secure identifiers
- Fixed-window rate limiting (6a) — cross-checked against a rate-limiting engineering write-up that names the exact boundary-burst trade-off, turning an unexamined choice into a documented one
- Operator-configured (not user-supplied) webhook URL (B2/6c) — confirmed against OWASP's SSRF guidance, which ties that risk specifically to user-controlled destinations

Full citations are in `REQUIREMENTS_ANALYSIS.md` §5 and §7.

## Post-completion review pass

Run as a dedicated, fresh critical read of every application file after
the build was otherwise "done" — not a re-assertion that prior review
still held. Found two real bugs and one undocumented decision:

1. **Structured logs weren't actually valid JSON** whenever a message
   contained a quote or newline — exactly what exception text (including
   the project's own failure-path warnings) commonly contains. Reproduced
   the failure directly before fixing it with a formatter that builds a
   real JSON payload rather than interpolating a string. Regression test
   added.
2. **The rate limiter's internal state grew without bound** — one entry
   per distinct client key ever seen, never evicted, a slow memory leak
   over a long-running process. Fixed with a periodic sweep that evicts
   expired entries; a test forces the sweep and asserts eviction actually
   happens.
3. **An open ambiguity from the very start of the project had never been
   given a written resolution**: what happens if the same URL is
   submitted twice? Verified the actual behavior directly (two identical
   submissions produce two different short codes) rather than assume it,
   then recorded it as a resolved assumption.

Re-verified after all fixes: full suite green, 100% coverage, and a
clean-room reinstall from a fresh virtual environment.
