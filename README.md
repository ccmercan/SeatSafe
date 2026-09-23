# SeatSafe

SeatSafe is a native iOS seat-reservation app and quality-engineering portfolio. It explores how to keep reservations correct through concurrency, retries, expired holds, network failures, and offline use.

## Demo — Phase 3 complete

Two iPhone simulators compete for one seat: one gets the temporary hold; the other sees
that the seat is unavailable. The demo skips the idle interval and leaves out the expected
happy path. Automated journey coverage is documented in the [Phase 3 evidence](docs/evidence/phase-3-ui-smoke.md).

![SeatSafe reservation conflict on two iPhone simulators](docs/media/seatsafe-two-iphone-demo.gif)

## Project status

### Phase 1 · Backend — complete

- FastAPI + PostgreSQL: migrations, deterministic demo data, request correlation, and Problem Details errors.
- Seat snapshot, hold, and reservation endpoints with database-backed idempotency.
- Database tests cover contention, request replay, distinct-key confirmations, and transaction rollback.

### Phase 2 · iOS client — complete

- iOS 17+ SwiftUI app with injected async services and Swift structured concurrency.
- Seat loading, selection, hold, confirmation, and persisted keys for safe retries—even after app-model recreation.
- Handles stale responses and cancellation; prevents duplicate in-flight actions. **21 deterministic unit tests.**

### Phase 3 · UI quality — complete

- Four XCUITest journeys: reservation, seat conflict, hold expiration, and API unavailable/retry.
- Tests use the real API and a disposable PostgreSQL database that the runner cleans up.
- Two consecutive successful runs; each passed all 21 unit tests and four UI journeys. See [test evidence](docs/evidence/phase-3-ui-smoke.md).

### Phase 4 · CI and release signals — not started

GitHub Actions, scheduled regressions, and CI artifact retention are next; no Phase 4 work is claimed yet.

## Why this project exists

The app stays intentionally small; the depth is in building and testing the system behind it:

- Native Swift/SwiftUI client
- Swift structured concurrency, cancellation, and UI-state isolation
- XCTest and XCUITest automation
- Python/FastAPI service
- PostgreSQL persistence and transaction guarantees
- API, integration, concurrency, accessibility, and performance testing
- CI quality gates, failure artifacts, and flake analysis (Phase 4)
- Architecture Decision Records and defect case studies

## Core user journey

```text
Discover event -> inspect event -> select seat -> hold seat
    -> confirm reservation -> retrieve it online or offline -> cancel
```

## Project guides

- [Product brief](docs/product-brief.md) · [Requirements](docs/engineering-requirements.md) · [Roadmap](docs/roadmap.md)
- [Test strategy](docs/test-strategy.md) · [Phase 2 evidence](docs/evidence/phase-2-concurrency.md) · [Phase 3 evidence](docs/evidence/phase-3-ui-smoke.md)
- [Learning plan](docs/learning-plan.md) · [Interview project defense](docs/interview-project-defense.md) · [Excalidraw diagrams](docs/diagrams/README.md)

<details>
<summary>Architecture decisions (ADRs 001–017)</summary>

- [ADR-001: Own the reservation backend](docs/decisions/001-own-the-reservation-backend.md)
- [ADR-002: Manage client work with structured concurrency](docs/decisions/002-swift-structured-concurrency.md)
- [ADR-003: Serialize seat transitions with row locks and constraints](docs/decisions/003-serialize-seat-transitions-with-row-locks.md)
- [ADR-004: Use disposable PostgreSQL test environments](docs/decisions/004-use-disposable-postgresql-test-environments.md)
- [ADR-005: Use thin routes, application services, and repositories](docs/decisions/005-use-thin-routes-services-and-repositories.md)
- [ADR-006: Model holds and reservations as separate records](docs/decisions/006-normalize-holds-and-reservations.md)
- [ADR-007: Use database-backed idempotency](docs/decisions/007-use-database-backed-idempotency.md)
- [ADR-008: Inject a server-configured demo user in Phase 1](docs/decisions/008-inject-a-configured-demo-user.md)
- [ADR-009: Standardize API errors with Problem Details](docs/decisions/009-standardize-api-problem-details.md)
- [ADR-010: Use Docker Desktop for local containers](docs/decisions/010-use-docker-desktop-for-local-containers.md)
- [ADR-011: Return one event-seat availability snapshot](docs/decisions/011-return-an-event-seat-availability-snapshot.md)
- [ADR-012: Set the minimum iOS deployment target to iOS 17](docs/decisions/012-set-ios-deployment-target.md)
- [ADR-013: Use lightweight SwiftUI feature models](docs/decisions/013-use-lightweight-swiftui-feature-models.md)
- [ADR-014: Use database-backed idempotency for hold creation](docs/decisions/014-use-idempotency-for-hold-creation.md)
- [ADR-015: Persist pending hold attempts locally](docs/decisions/015-persist-pending-hold-attempt-locally.md)
- [ADR-016: Persist the hold and confirmation key locally](docs/decisions/016-persist-pending-confirmation-locally.md)
- [ADR-017: Run UI smoke tests against a disposable backend](docs/decisions/017-use-disposable-backend-for-ui-smoke-tests.md)

</details>

## Planned repository shape

Key areas of the codebase:

```text
ios/                 Native application and Apple-platform tests
backend/             FastAPI service and backend tests
performance/         Load and contention scenarios
infrastructure/      Local environment and CI support
docs/                Requirements, decisions, strategy, and evidence
```

## Working agreement

This is a learning-first project. Major decisions are compared, recorded, and validated before implementation. See [AGENTS.md](AGENTS.md) for the project workflow.

## Concurrency guarantee

PostgreSQL permits only one active hold per event-seat. A row lock serializes competing
customers; idempotency handles retries by one customer, not conflicts between different
customers. See [ADR-003](docs/decisions/003-serialize-seat-transitions-with-row-locks.md),
[ADR-007](docs/decisions/007-use-database-backed-idempotency.md), and the [Phase 2 evidence](docs/evidence/phase-2-concurrency.md).
