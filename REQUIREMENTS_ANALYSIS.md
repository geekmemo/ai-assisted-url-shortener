# Requirements Analysis & Design Rationale

## 1. Problem statement

**Raw requirement:** build a URL shortener service with core APIs,
analytics, and reliability features.

As given, this statement under-specifies several dimensions that
materially affect design: identity/ownership model, link lifecycle,
consistency requirements for analytics, and collision-resolution
strategy. Rather than resolve these implicitly, each was treated as an
explicit design decision with a stated rationale (Section 3).

**Normalized problem statement:** a service that (a) accepts a long URL
and returns a short, collision-free alias; (b) redirects the alias to
the original URL with minimal latency; (c) records per-alias access
analytics without impacting redirect latency or availability; (d)
remains correct under concurrent writes; (e) degrades gracefully under
load and under partial failure of non-critical subsystems.

## 2. Functional scope

| In scope | Out of scope (see Section 3 for rationale) |
|---|---|
| Short link creation with collision-safe generation | Authentication / per-user ownership |
| Redirect with click analytics | Link expiry |
| Per-IP rate limiting | Real-time/streaming analytics |
| Outbound webhook on link creation (brownfield) | Multi-tenancy |
| Structured logging with request correlation (ambiguous-scenario resolution) | Horizontal scale-out / distributed datastore |

## 3. Assumptions and their rationale

| Assumption | Rationale |
|---|---|
| Anonymous, no-auth links | Auth is an orthogonal concern (identity/session management) with its own design surface; adding it speculatively would expand scope without a stated requirement driving it. Treated as a named extension point. |
| No link expiry | No lifecycle requirement was stated; adding TTL/expiry logic pre-emptively risks building against unstated constraints (e.g. retention policy, legal hold) that would need to be gathered, not assumed. |
| Eventually-consistent analytics | The requirement asks for "analytics," not "real-time analytics." A strongly-consistent, low-latency counter is achievable without a streaming pipeline; committing to eventual consistency avoids a disproportionate infrastructure cost (message queue, stream processor) for an unstated latency SLA. |
| Generate-and-retry collision handling, not pre-reserved counter-based IDs | At prototype scale, the probability of collision with a 7-character base62 keyspace (~3.5 × 10¹² combinations) is negligible; a counter-based scheme would add a coordination point (e.g. a distributed sequence generator) that solves a problem this scale doesn't have. |
| Single-process deployment | No horizontal-scale requirement was stated. Rate limiting and in-memory state are explicitly scoped to single-instance operation; documented as a limitation, not hidden. |

## 4. Non-functional requirements addressed

### 4.1 Reliability

- **Atomicity under concurrency**: click-count increments use a single
  SQL-level `UPDATE ... SET count = count + 1` rather than an
  application-level read-modify-write, eliminating a lost-update race.
  Verified with both an in-process concurrent-thread test and a live
  multi-process concurrent HTTP test against a running server.
- **Fault isolation**: failures in non-critical side effects (analytics
  write, outbound webhook delivery) are caught and logged, and never
  propagate to fail the primary request (link creation or redirect).
  This is validated by tests that deliberately inject failures into
  those code paths and assert the primary response is unaffected.
- **Graceful degradation under load**: a configurable per-IP rate
  limiter returns `429` past a threshold rather than allowing unbounded
  request volume to degrade the service for all clients.

### 4.2 Security

- **Non-predictable identifiers**: short codes are generated with a
  cryptographically secure source (`secrets`), not a general-purpose
  PRNG, to prevent enumeration/guessing of other users' links.
- **Input validation at the trust boundary**: `long_url` is validated
  as a well-formed URL and bounded in length at the application layer,
  compensating for the fact that the underlying datastore (SQLite) does
  not enforce column-length constraints — this was verified empirically,
  not assumed.
- **No client-supplied trust for security-relevant identifiers**: the
  rate limiter keys on the transport-level connection IP rather than a
  client-supplied header (e.g. `X-Forwarded-For`), which would allow
  trivial bypass by a malicious client absent a trusted reverse proxy.
- **Outbound-call risk containment**: the webhook target URL is an
  operator-configured value (environment variable), never accepted as
  per-request user input — avoiding a server-side request forgery (SSRF)
  vector that would exist if a caller could supply an arbitrary webhook
  destination.

### 4.3 Observability

- Structured (single-line JSON) logs for every request, carrying a
  correlation identifier that is either generated per request or
  propagated from an inbound `X-Request-ID` header, and echoed back to
  the caller — enabling request-level tracing across client and server
  logs without a distributed tracing backend.
- Failure paths that are deliberately non-fatal to the caller (analytics
  write failures, webhook delivery failures) are still surfaced as
  logged warnings, so operational visibility is not traded away for
  request-level resilience.

### 4.4 Testability

- 100% line coverage across all application modules, with a test suite
  that includes concurrency, failure-injection, and route-precedence
  regression tests — not only happy-path assertions.
- A shared test fixture reloads every module holding process-level state
  (configuration, database engine, rate limiter, webhook settings)
  between tests, preventing state leakage across test cases.

## 5. Design decisions and alternatives considered

| Decision | Alternative considered | Why this was chosen |
|---|---|---|
| SQLite | NoSQL document/key-value store (as recommended by a standard system-design reference [1] for services at 30M-user scale) | The referenced recommendation is scale-driven, not correctness-driven; it targets a load profile this system is not required to meet. A relational store with a real schema and constraints is the better fit at this scope, and keeps the door open to a managed relational service later without a data-model rewrite. |
| Generate-and-retry short code assignment, using a CSPRNG (`secrets`) | Pre-reserved sequential/counter-based IDs; a general-purpose PRNG (`random`) | Retry avoids a shared-counter coordination point at this keyspace size and scale. CSPRNG use follows the same principle OWASP's session-management guidance [2] applies to session identifiers: a non-cryptographic PRNG admits statistical prediction of "random" values, which for a public redirect service means enumerable/guessable links. |
| In-memory fixed-window rate limiter | External rate-limiting service / shared cache (e.g. Redis); sliding-window counter | Appropriate for a single-instance deployment; a shared backend would add operational surface area disproportionate to the stated scope. Fixed-window was chosen over a sliding-window counter with awareness of its documented weakness [3] — traffic can burst through right at a window boundary — accepted as a reasonable trade-off for simplicity at this scale, not an oversight (see the risk register). |
| `BackgroundTasks` for webhook dispatch, with an operator-configured (not user-supplied) target URL | Synchronous outbound call within the request; user-supplied webhook URL | A synchronous call would couple the caller's request latency and success to an external system's availability. Restricting the target to an operator-set value, rather than accepting one per request, follows OWASP's SSRF guidance [4]: SSRF risk specifically arises from *user-controlled* destinations, and an application-configured value falls outside that threat model. |
| FastAPI `lifespan` context manager for startup logic | `@app.on_event("startup")` | FastAPI's own documentation [5] states `on_event` is deprecated in favor of `lifespan`, and that the two cannot be mixed — not a stylistic preference. |

## 6. Risk register

| Risk | Likelihood at current scope | Impact if realized | Mitigation |
|---|---|---|---|
| Lost analytics updates under concurrency | Low (mitigated) | Undercounted clicks | Atomic SQL update; verified under real concurrent load |
| Short-code enumeration/guessing | Low (mitigated) | Unauthorized access to a link's destination | Cryptographically secure generation, per OWASP guidance on identifier randomness [2] |
| Outbound webhook target abused for SSRF | Not applicable at current scope | N/A | Webhook URL is operator-set, not user-supplied — outside the threat model OWASP's SSRF guidance [4] targets; flagged as a required control if this ever becomes user-configurable |
| Rate limiter state lost on restart / not shared across instances | Certain, by design | Rate limiting resets on restart; ineffective if horizontally scaled | Explicitly documented limitation; requires a shared backend before multi-instance deployment |
| Fixed-window rate limiting allows a burst of traffic exactly at window-reset boundaries [3] | Low impact at current scale | Brief over-admission of requests around the reset instant | Accepted trade-off for simplicity over a sliding-window counter; would reconsider if abuse at boundaries were observed in practice |
| No schema migration tooling | Certain, by design | Manual intervention required for future schema changes against existing data | Acceptable for a greenfield prototype with no production data; flagged as required before further schema evolution against live data |

## 7. External references

1. [System Design: URL Shortening Service](https://www.geeksforgeeks.org/system-design/system-design-url-shortening-service/) — used to cross-check schema sizing (`long_url` length, `short_code` length/entropy) and collision-handling approach; the NoSQL-at-scale recommendation was reviewed and deliberately not followed (see Section 5).
2. [OWASP Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) — the CSPRNG requirement for session identifiers is the same principle applied here to short-code generation: predictable "random" values are a guessing/enumeration risk for any security-relevant identifier, not only session tokens.
3. [Cloudflare Engineering: Counting things, a lot of different things](https://blog.cloudflare.com/counting-things-a-lot-of-different-things/) — documents the fixed-window rate limiter's known boundary-burst weakness and compares it against sliding-window log/counter approaches; used to make an informed, not accidental, choice of fixed-window for this project's scope.
4. [OWASP Server-Side Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) — confirms SSRF risk is specifically tied to user-controlled request destinations, which grounds the decision to keep `webhook_url` operator-configured rather than accepting it as request input.
5. [FastAPI: Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) — official documentation confirming `on_event` is deprecated in favor of the `lifespan` context manager.
