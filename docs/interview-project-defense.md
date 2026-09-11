# Interview project defense

This is a living evidence record, not a script. Add answers only after the underlying work has been completed and verified.

## Thirty-second overview

Current draft:

> SeatSafe is a native iOS reservation application with a Python and PostgreSQL backend. I built it to explore the quality risks hidden behind a simple booking flow: concurrent users choosing the same seat, expired holds, retries, offline state, and unreliable UI automation. The project uses layered tests and CI quality gates, with architecture decisions and defect investigations documented in the repository.

Revise this after implementation so every statement describes completed work.

## Decision record

### Why not use a real seating API?

Status: ADR-001 accepted on 2026-09-11; implementation evidence remains pending.

Draft answer:

> I considered a commercial ticketing API, a public event feed, and a local service. The project required deterministic test data, state reset, controlled failures, and visibility into transaction behavior. A third-party API would make those tests dependent on mutable inventory and provider availability. I chose to own a small FastAPI and PostgreSQL backend, while keeping the event source behind a boundary that could support a read-only provider later.

Evidence to add:

- Accepted ADR link
- Seed/reset command
- Concurrent test result
- CI run without commercial credentials

### How will the system prevent double booking?

Status: ADR-003 accepted on 2026-09-11; implementation evidence remains pending.

Draft answer:

> An application-level availability check is vulnerable to a race because two requests can read the same available state. SeatSafe will lock the authoritative event-seat row during each hold or confirmation transition and keep that transaction short. A database uniqueness constraint provides final protection against multiple active reservations. Concurrent PostgreSQL integration tests will prove the behavior and verify the losing request receives a defined conflict.

Evidence to add:

- Schema models and initial migration created on 2026-09-11
- Concurrent integration-test command and result
- Conflict-response contract
- Relevant transaction diagnostics

### How will integration tests remain deterministic?

Status: ADR-004 accepted on 2026-09-11; implementation evidence remains pending.

Draft answer:

> The integration suite will create a disposable PostgreSQL environment, initialize it with the production migrations, and reset and seed stable scenarios through test-harness database fixtures. Concurrency tests will use independent connections so they exercise real commit visibility. Reset capability stays outside the application API, and the harness must refuse to target a database that is not explicitly configured for testing.

Evidence to add:

- Environment startup and teardown commands
- Migration command and result
- Repeatability or randomized-order test result
- Unsafe-target rejection test

### How is the backend organized?

Status: ADR-005 accepted on 2026-09-11; implementation evidence remains pending.

Draft answer:

> FastAPI routes handle HTTP validation and mapping, application services coordinate complete use cases and own their transaction boundaries, and repositories perform PostgreSQL operations inside those transactions. This lets unit tests exercise business decisions without HTTP while integration tests retain responsibility for proving SQL constraints and locking. I avoided both route-level SQL and a full hexagonal architecture because the first obscures responsibilities and the second adds unnecessary ceremony for this product.

Evidence to add:

- One implemented request trace from route to commit
- Service unit tests
- API contract tests
- PostgreSQL repository integration tests

### Why are holds and reservations separate records?

Status: ADR-006 accepted on 2026-09-11; implementation evidence remains pending.

Draft answer:

> A seat is the stable resource, a hold is a temporary claim, and a reservation is the confirmed outcome. Storing them separately preserves history and makes expiration and cancellation explicit. During a transition, the service locks the stable event-seat row and evaluates the related active records. Partial unique indexes prevent multiple active holds or reservations, while old expired or cancelled records remain available for debugging and audit.

Evidence to add:

- Migration and relationship diagram
- Lifecycle service tests
- Constraint integration tests
- Expired-hold replacement test

### How does confirmation remain safe when a request is retried?

Status: ADR-007 accepted on 2026-09-11; implementation evidence remains pending.

Draft answer:

> The client supplies one stable idempotency key for a logical confirmation attempt. PostgreSQL stores that key with a fingerprint of the request and the logical result. A retry with the same key and input receives the original reservation result, while reuse with different input is rejected. This is separate from the active-reservation constraint: idempotency gives one request a stable answer, while the seat constraint protects against competing requests that use different keys.

Evidence to add:

- Confirmation API contract
- Same-key replay test
- Changed-payload rejection test
- Concurrent same-key and different-key test results

### How does Phase 1 identify the current user?

Status: ADR-008 accepted on 2026-09-11; implementation evidence remains pending.

Draft answer:

> Phase 1 deliberately defers production authentication. FastAPI injects a server-configured demo identity into each route, and application services receive that identity explicitly when enforcing hold ownership. Tests can replace the identity dependency to simulate Alice and Bob, but normal callers cannot choose a trusted user through a request header. A future authentication provider can replace this dependency without changing reservation rules.

Evidence to add:

- Identity dependency implementation
- Hold-owner authorization service test
- API dependency-override test
- README authentication limitation

### How are API errors made useful to people and clients?

Status: ADR-009 accepted on 2026-09-11; implementation evidence remains pending.

Draft answer:

> Expected failures use the standard Problem Details shape. The HTTP status describes the broad protocol result, a stable SeatSafe code drives client behavior, and the detail gives a readable explanation. A correlation identifier connects the response to server logs. This prevents the iOS client and tests from parsing English text and keeps HTTP mapping outside domain services.

Evidence to add:

- Problem Details schema and handler implementation
- Domain-error contract test
- Validation-error contract test
- Correlation response-and-log test

### How is PostgreSQL isolated locally?

Status: ADR-010 accepted; the local environment, migration, and initial integration tests were validated on 2026-09-11.

Draft answer:

> Local PostgreSQL runs in a disposable container managed through Docker Desktop and Compose. This makes the database version and configuration repeatable, keeps test data separate from a personal database, and lets a developer inspect container state and logs visually. CI can use its own compatible container service because Docker Desktop itself is only the local runtime.

Evidence to add:

- Compose configuration validated on 2026-09-11
- PostgreSQL 17.11 readiness query completed on 2026-09-11
- Integration-test startup and teardown commands documented in `backend/README.md`
- Disposable `tmpfs` environment was removed successfully after validation

## Questions to answer as the project develops

### Product and scope

- Why is the application intentionally small?
- Which behaviors were deliberately excluded?
- What would make an external event integration worth adding?

### Backend and data

- How does the system prevent double booking?
- Why is a hold separate from a reservation?
- How are expired holds handled?
- What makes a retry safe?
- Which guarantees belong in Python and which belong in PostgreSQL?

### iOS architecture

- Why SwiftUI?
- How are networking, persistence, identifiers, and time injected?
- How does the client represent loading, stale, conflict, and offline states?
- Why use XCTest, XCUITest, or Swift Testing for each type of behavior?
- Which asynchronous work is owned by a screen or view model, and when is it cancelled?
- How do late responses avoid overwriting newer UI state?
- Why is `@MainActor` appropriate for observable UI state?
- Where would an actor help, and where would it add unnecessary complexity?
- What happens if local cancellation occurs after the server accepts a reservation?
- Why does client-side duplicate suppression not replace server idempotency?

### Automation

- Why is a test at the unit, integration, API, or UI layer?
- How is test data made deterministic?
- How do UI tests wait for state without fixed sleeps?
- How is flakiness measured and handled?
- What artifacts make a failed CI run diagnosable?

### Scale and limitations

- What evidence applies only to a local portfolio environment?
- What would change with multiple service instances or regions?
- Which performance conclusions cannot yet be made?
- What technical debt was consciously accepted?

## Defect story template

For each important defect:

```text
Symptom:
User or business impact:
How it was reproduced:
Evidence collected:
Root cause:
Why existing tests missed it:
Fix:
Regression protection:
Remaining risk:
What I would explain in an interview:
```

## Metrics ledger

Record a metric only with reproducible evidence:

| Metric | Value | Environment | Command or CI link | Date |
|---|---:|---|---|---|
| Backend foundation tests | 6 passed in 0.38 s | macOS, Python 3.12.0, pytest 9.1.1 | `cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest` | 2026-09-11 |
| PostgreSQL container readiness | Healthy; query returned PostgreSQL 17.11 | Docker Desktop 29.7.2, Compose 5.5.1, Apple Silicon | `docker compose -f infrastructure/compose.test.yaml up -d --wait` followed by the documented `psql` readiness query | 2026-09-11 |
| Backend unit and API checkpoint | 9 passed; 1 integration test deselected | Project `.venv`, Python 3.12.0, pytest 9.1.1 | `cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p pytest_asyncio.plugin -m 'not integration' -v` | 2026-09-11 |
| Initial schema integration checkpoint | 1 passed in 1.15 s | PostgreSQL 17.11 disposable container | `cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p pytest_asyncio.plugin -m integration -v` | 2026-09-11 |
| Hold-creation checkpoint | 19 passed in 0.71 s; 2 dependency deprecation warnings | PostgreSQL 17.11, Python 3.12.0, non-synced temporary virtual environment | `cd backend && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /private/tmp/seatsafe-venv/bin/python -m pytest -p pytest_asyncio.plugin -q` | 2026-09-11 |
