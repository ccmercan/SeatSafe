# SeatSafe

SeatSafe is a native iOS event-seat reservation application and a production-style quality engineering portfolio project. Its central engineering challenge is preserving correct reservation behavior under concurrency, retries, expired holds, network failures, and offline access.

## Current status

**Phase 1: reservation-core vertical slice complete.** The FastAPI service includes
configuration, demo identity injection, correlation IDs, Problem Details responses, the
initial PostgreSQL migration, deterministic demo seeding,
`GET /v1/events/{event_id}/seats`, `POST /v1/holds`, and
`POST /v1/reservations` with database-backed idempotency. PostgreSQL tests cover
competing hold requests, same-key replay, different-key confirmation attempts, and
transaction rollback after a real database constraint failure. The full backend suite
passes with 41 tests. Phase 2 begins after review of proposed ADR-002.

## Why this project exists

The visible application is intentionally small. The engineering depth comes from owning both the system and its quality infrastructure:

- Native Swift/SwiftUI client
- Swift structured concurrency, cancellation, and UI-state isolation
- XCTest and XCUITest automation
- Python/FastAPI service
- PostgreSQL persistence and transaction guarantees
- API, integration, concurrency, accessibility, and performance testing
- Continuous integration, failure artifacts, quality gates, and flake analysis
- Architecture Decision Records and defect case studies

## Core user journey

```text
Discover event -> inspect event -> select seat -> hold seat
    -> confirm reservation -> retrieve it online or offline -> cancel
```

## Documentation

- [Product brief](docs/product-brief.md)
- [Engineering requirements](docs/engineering-requirements.md)
- [Test strategy](docs/test-strategy.md)
- [Learning plan](docs/learning-plan.md)
- [Roadmap](docs/roadmap.md)
- [Interview project defense](docs/interview-project-defense.md)
- [Editable Excalidraw visual learning pack](docs/diagrams/README.md)
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

## Planned repository shape

The implementation structure will be finalized through ADRs before it is created:

```text
ios/                 Native application and Apple-platform tests
backend/             FastAPI service and backend tests
performance/         Load and contention scenarios
infrastructure/      Local environment and CI support
docs/                Requirements, decisions, strategy, and evidence
```

## Working agreement

This is a learning-first project. Major decisions are discussed, compared, recorded, and validated before implementation. See [AGENTS.md](AGENTS.md) for the collaboration rules applied to future Codex tasks.

## Next decision

Review proposed ADR-002 and decide the client concurrency approach before starting the
native iOS vertical slice. The database permits only one active hold per event-seat, so
the tested race is between two hold requests; exactly one request creates the valid hold
that may then be confirmed.
