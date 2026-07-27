# Final Engineering Summary

## Plan and rationale

The requirement ("build a URL shortener with core APIs, analytics, and
reliability features") was normalized into 8 sequenced greenfield tasks
(scaffold → data model → create → redirect → analytics → rate limiting →
tests → traceability), each with explicit acceptance criteria agreed
before implementation, not inferred after the fact. Two further scenarios
were executed on top of that stable base: a brownfield enhancement
(webhook notification on link creation) and an ambiguous-requirement
scenario ("make it enterprise-ready," deliberately vague, resolved to a
concrete observability slice). See `REQUIREMENTS_ANALYSIS.md` for the
full requirement decomposition, scope assumptions, and design rationale;
every AI-generated piece of code went through a recorded accept/edit/
reject decision with a stated reason, not a blanket approval (see
`AI_PROMPTING_FRAMEWORK.md` for the discipline this was run under).

Python/FastAPI/SQLAlchemy/SQLite/pytest was chosen because it matches
current hands-on production experience (voice AI orchestration, workflow
automation, Python + Azure microservices) rather than being picked cold
under time pressure, and because Python's straightforward syntax makes
AI-generated vs. human-edited code lineage easy to show clearly — which
matters given this assessment's explicit focus on AI-assisted execution
traceability, not just the resulting code.

## Artifacts

- **Working prototype**: `app/` — FastAPI service with `/health`,
  `POST /shorten`, `GET /{short_code}`, click analytics, per-IP rate
  limiting, an opt-in creation webhook, and structured request logging.
- **Tests**: `tests/` — 32 tests, 100% line coverage across all
  application modules, including concurrency tests (25-thread and a live
  20-process concurrent test), a route-shadowing regression test, and
  resilience tests that deliberately force failures (DB commit errors,
  webhook network errors) to prove the system degrades the way it's
  documented to, not just that the happy path works.
- **Docs**: `README.md` (setup/run/test/API/config), `ARCHITECTURE.md`
  (components, control flow, key decisions), `REQUIREMENTS_ANALYSIS.md`
  (requirement decomposition, assumptions, design rationale, risk
  register), `AI_PROMPTING_FRAMEWORK.md` (prompting discipline,
  guardrails, security, responsible AI), this file.

## Risks, trade-offs, and validation

| Risk / trade-off | Mitigation / validation |
|---|---|
| Lost updates to `click_count` under concurrent redirects | Atomic SQL-level `UPDATE` instead of Python read-modify-write; validated with a 25-thread in-process test *and* 20 real concurrent OS processes against a live server |
| SQLite doesn't enforce `VARCHAR(N)` length at the DB level (verified directly, not assumed) | Real enforcement moved to the application layer: Pydantic's `HttpUrl` + an explicit max-length validator, both covered by tests that specifically target the gap between Pydantic's own 2083-char cap and this app's 2048-char limit |
| A broken analytics write or unreachable webhook could break the user-facing request | Both wrapped so failures are caught, rolled back where relevant, and never propagate to the caller; both paths have a dedicated test that *forces* the failure and asserts the primary response still succeeds |
| Predictable/guessable short codes | `secrets.choice()`, not `random`, for code generation — rejected during Task 3 review specifically because `random` isn't cryptographically secure |
| `X-Forwarded-For` spoofing could bypass rate limiting | Deliberately not trusted; IP is read from the actual transport-level connection (`request.client.host`), since there's no known/trusted reverse proxy in front of this prototype |
| Test isolation gaps caused by shared module-level singletons (rate limiter, webhook settings) | Found twice during development (Task 6, ambiguous-scenario logging), root-caused both times, and fixed by consolidating into a single `tests/conftest.py` fixture that reloads every stateful module together, rather than patching symptoms per-file |
| Schema sizing (`long_url` length, `short_code` length/entropy) chosen without external validation | Cross-checked against a standard system-design reference *after* the fact; both figures matched exactly, and one deliberate divergence (SQLite vs. the reference's NoSQL-at-scale recommendation) was identified and documented rather than silently accepted or blindly followed |
| Structured logs weren't actually valid JSON when a message contained a quote or newline — found in a dedicated post-completion review pass, not by a bug report | Reproduced the failure directly (`json.loads` raising on a realistic exception message) before fixing it; replaced string-interpolated log formatting with a real `json.dumps`-based formatter, with a regression test covering the exact failure case |
| Rate limiter's in-memory dict grew by one entry per distinct client key ever seen, with no eviction — same review pass | Added a periodic sweep that evicts expired entries, with a test that forces the sweep and asserts stale keys are actually removed |

## Assumptions

- Anonymous, no-auth links (auth is a named extension point, not built)
- No link expiry
- Eventually-consistent analytics is acceptable (no real-time streaming requirement)
- Collision handling via generate-and-retry with a capped attempt count, not pre-reserved counter-based IDs
- No deduplication of `long_url` — each `/shorten` call gets its own new `short_code`, even for a URL submitted before (verified directly, not assumed)
- Single-process deployment (rate limiter and in-memory state assume one instance)
- `webhook_url` is operator-configured, never user-supplied per request (relevant to the SSRF risk assessment in the brownfield scenario)

## Limitations

- **No schema migrations** — `create_all()` only creates missing tables;
  a real schema change to an existing column would require a manual
  drop/recreate of the dev database. Acceptable for a from-scratch
  prototype with no production data; would need Alembic (or equivalent)
  before this could evolve safely in production.
- **Rate limiting and the webhook queue are both in-memory** — neither
  survives a process restart, and neither works correctly across
  multiple instances without a shared backend (e.g. Redis). Named
  explicitly rather than left implicit.
- **Fixed-window rate limiting allows a burst of traffic at window-reset
  boundaries** — a documented, known weakness of this algorithm relative
  to a sliding-window counter (see reference [3] in
  `REQUIREMENTS_ANALYSIS.md`). Accepted deliberately for simplicity at
  this scale; would be reconsidered if boundary abuse were observed in
  practice.
- **No authentication/authorization, no multi-tenancy** — every link is
  anonymous and globally visible to anyone who has (or guesses) its
  short code. This was a stated MVP scope decision, not an oversight.
- **No metrics/tracing backend** — structured logs exist and carry a
  correlation ID, but there's no Prometheus/Grafana/OpenTelemetry
  integration; the ambiguous-scenario work deliberately scoped
  observability down to what's implementable and valuable at this
  project's size, and named the rest as future work rather than
  building a placeholder integration with nothing behind it.

## Assignment scope coverage

The assignment's stated scope (§3) names four categories this project
is expected to cover. All four are addressed, not just the two that
would come from a from-scratch build alone:

| Scope item | Where it's covered |
|---|---|
| Greenfield scenarios (new systems/features) | The 8-task base build — `TRACEABILITY.md` entries 1a-7f |
| Brownfield scenarios (enhancements, refactors, bug fixes) | The webhook enhancement to the existing `/shorten` endpoint (`TRACEABILITY.md` B1-B6); the post-completion review pass that found and fixed two real bugs and added linting counts as refactor/bug-fix work on top of already-shipped code, not new-system work |
| Test and documentation improvements | Two coverage gaps investigated and closed in Task 7 (not just a coverage number); linting added as a previously-missing quality gate; five documentation files iterated on for accuracy and completeness across multiple review passes |
| Well-defined and ambiguous requirements | Tasks 1-6 had explicit, well-defined acceptance criteria agreed before implementation; "make it enterprise-ready" (`TRACEABILITY.md` A1-A6) was deliberately ambiguous and required explicit interpretation and scoping before any code was written |

## Evaluation criteria quick reference

This table is a lookup aid for verifying a specific claim after the fact
— it is not a substitute for walking through the reasoning behind these
decisions, which is the point of a technical walkthrough discussion.

| Evaluation criterion | Where to look |
|---|---|
| Effectiveness of AI-assisted execution | `TRACEABILITY.md` (accept/edit/reject with rationale per change) |
| Architecture/system design quality | `ARCHITECTURE.md` (component + sequence diagrams, key decisions) |
| Depth of decomposition and execution quality | `REQUIREMENTS_ANALYSIS.md` §2 (scope table), `TRACEABILITY.md` (greenfield/brownfield/ambiguous task-by-task record) |
| Realism/quality of outputs | `tests/` (32 tests, 100% coverage); every endpoint boot-verified against a live server, not just unit-tested |
| Validation and risk management rigor | `REQUIREMENTS_ANALYSIS.md` §6 (risk register, including two issues found and fixed during review) |
| Clarity and defensibility of decisions | `REQUIREMENTS_ANALYSIS.md` §5 and §7 (decisions with alternatives considered and external references) |
| Modular / testable / reliable / secure / scalable / safe change management | Modular: one file per concern in `app/`. Testable: 100% coverage, linting clean. Reliable: atomic updates, fault-isolated side effects. Secure: CSPRNG, SSRF-aware webhook design, OWASP references. Scalable: documented single-process limitation with a stated path forward. Safe change management: one commit per task, nothing pushed without review |
| Engineering judgment | Rejected AI drafts and root-caused bugs throughout `TRACEABILITY.md`, not just accepted output |
