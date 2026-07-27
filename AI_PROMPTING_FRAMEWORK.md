# AI Prompting Framework

This document specifies the prompting discipline, grounding requirements,
guardrails, and responsible-AI practices applied throughout this project's
development. It is a control document, not a retrospective: every rule
below was applied *during* development, and violations were caught and
corrected in `TRACEABILITY.md`, not discovered after the fact.

## 1. Task-prompt structure

Every implementation task was framed to the AI assistant with four
explicit components before any code generation occurred:

| Component | Purpose | Example (Task 5, analytics) |
|---|---|---|
| **Intent** | What outcome is wanted, in engineering terms | Record click count and timestamp per redirect |
| **Constraints** | Non-negotiable properties the solution must satisfy | Must remain correct under concurrent requests; must not block the redirect on failure |
| **Acceptance criteria** | Falsifiable conditions that prove the task is done | Click count increments atomically under concurrent hits (tested with both threaded and multi-process concurrent load) |
| **Technical context** | Relevant existing code, conventions, and prior decisions | Existing `Link` model, SQLite backend, established convention that config constants live in `app/config.py` |

Ambiguous or underspecified requests (e.g. "make it enterprise-ready")
were never implemented directly from the raw prompt. They were first
decomposed into named candidate interpretations, one interpretation was
selected with a stated rationale, and the rest were explicitly recorded
as out of scope — never silently assumed away.

## 2. Grounded reasoning requirements

The assistant was required to verify claims against the actual system
state rather than assert them from documentation, memory, or plausible-
sounding defaults. Concretely, this project applied:

- **Verify before recommending.** A claim that a file, function, or
  behavior exists was checked against the live filesystem/codebase
  before being acted on. (Example: a prior session's documentation
  claimed a scaffold was "complete"; the actual directory was checked
  and found empty before any further work proceeded.)
- **Boot-verify, don't just unit-test.** Every task was validated with a
  real running process and real HTTP calls (`curl`, independent client
  processes), in addition to in-process test-client assertions — because
  a passing unit test can mask an integration-level failure a live
  process would surface (e.g. startup ordering, real concurrency,
  cross-process state).
- **Investigate coverage gaps rather than dismiss them.** When
  measured test coverage revealed two uncovered lines, both were
  root-caused rather than papered over with an incidental test; one
  turned out to reveal a test that was passing for the wrong reason
  entirely (an upstream library's validation firing before this
  project's own validation logic ever ran).
- **Cross-check design decisions against external references** where a
  credible standard exists, and explicitly reconcile any divergence
  (a system-design reference's schema-sizing recommendations were
  cross-checked and matched; its NoSQL-at-scale recommendation was
  deliberately not followed, with the scale-mismatch reasoning
  documented rather than silently ignored or blindly adopted).
- **Re-verify after every fix.** A fix was never assumed correct on
  first pass; the relevant test(s) were re-run, and in concurrency-
  sensitive cases, re-run multiple times and in reordered sequences to
  rule out flakiness before being considered settled.

## 3. Guardrails

- **Human sign-off gates.** Irreversible or externally-visible actions
  — git pushes, deleting cached credentials, installing a system-wide
  interpreter, force-clearing another account's state — were proposed
  and explicitly confirmed before execution, not assumed as implied
  consent from an earlier, narrower approval.
- **Scope discipline.** No task added functionality, abstraction, or
  configuration beyond what its stated acceptance criteria required.
  An AI-generated config field belonging to a later task was rejected
  and removed during review rather than kept "since it might be
  useful."
- **Confidentiality boundaries.** A source document carrying an
  internal-use classification marking was identified before any
  version-control action and explicitly excluded from the public
  repository, rather than committed by default.
- **No destructive operations without explicit confirmation.** Actions
  with a meaningful blast radius (overwriting credentials, force-
  pushing, deleting untracked work) were never taken opportunistically
  to resolve a blocker; the underlying cause was diagnosed and a
  reversible or explicitly-approved path was used instead.

## 4. Security practices for AI-assisted development

- **No secrets, credentials, or confidential source material entered
  the AI's working context** as part of prompts, generated code, or
  logs.
- **Every AI-generated function was reviewed before acceptance** —
  including functions that were ultimately accepted unmodified — with
  the review decision and rationale recorded, so "the AI wrote it" is
  never the reason a piece of code shipped.
- **Cryptographic vs. general-purpose randomness was treated as a
  security-relevant distinction**, not an implementation detail: an
  AI-generated first draft using a general-purpose PRNG for
  identifier generation was rejected specifically because predictable
  identifiers are an enumeration risk in a public-facing service.
- **Trust-boundary validation was pushed to the point closest to the
  boundary**, and verified rather than assumed — the underlying
  datastore's actual constraint-enforcement behavior was tested
  directly rather than inferred from its schema declaration, and
  application-level validation was added specifically to close the gap
  that testing revealed.
- **Client-supplied data was never trusted for security-relevant
  decisions** (e.g. a spoofable HTTP header was deliberately not used
  as the basis for rate-limiting identity).
- **Dependencies were pinned to exact, installed versions** rather than
  left floating, and reproducibility was verified with a clean-room
  reinstall before each milestone was considered complete.

## 5. Responsible AI principles

- **Engineer-led execution, AI as accelerator.** Per the governing
  principle of this exercise, the AI assistant generated candidate
  implementations, tests, and documentation; the engineer retained
  ownership of every accept/edit/reject decision, and of overall
  correctness, maintainability, and production-readiness. Nothing was
  auto-committed or auto-merged without review.
- **Full traceability, including negative outcomes.** `TRACEABILITY.md`
  records rejections, bugs found in AI-generated code, and judgment
  calls that diverged from the AI's first suggestion, not only
  successful outcomes — because a log that only records successes is
  not a credible account of the process.
- **No fabricated confidence.** Where the assistant was uncertain of a
  runtime detail (e.g. the exact ordering semantics of a framework's
  middleware stack, or whether background-task execution timing was
  guaranteed relative to a context variable's lifecycle), the design
  was changed to avoid depending on the uncertain behavior, or the
  behavior was empirically verified, rather than asserting a
  remembered-but-unverified fact.
- **Limitations are named, not hidden.** Every deliberate scope
  boundary (no auth, no horizontal scale-out, no migration tooling, no
  metrics backend) is documented as a limitation in
  `ENGINEERING_SUMMARY.md`, distinct from an oversight.
