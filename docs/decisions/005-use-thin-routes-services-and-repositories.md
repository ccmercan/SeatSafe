# ADR-005: Use thin routes, application services, and repositories

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

The SeatSafe backend must expose HTTP endpoints, enforce hold and reservation rules, and execute PostgreSQL transactions. These responsibilities need boundaries that support focused tests and make transaction ownership visible without introducing architecture that is disproportionate to the application.

The design must support dependency injection, deterministic clocks and identifiers, PostgreSQL row locking, clear domain failures, and HTTP error mapping.

## Options considered

### Option A: FastAPI routes execute business rules and database operations directly

Advantages:

- Minimal initial file structure
- Easy to trace in a very small prototype

Disadvantages:

- Couples HTTP concerns to domain and persistence behavior
- Makes focused unit tests difficult
- Encourages transaction handling to spread across routes
- Becomes harder to reuse reservation behavior outside HTTP

### Option B: Thin routes, application services, and repositories

Routes translate HTTP requests and responses. Application services coordinate use cases and transactions. Repositories perform persistence operations using the service-owned transaction.

Advantages:

- Gives each layer a small, explainable responsibility
- Supports service tests with controllable dependencies
- Keeps HTTP error mapping separate from business decisions
- Makes transaction boundaries explicit at the use-case level
- Allows real repository and database behavior to be integration tested

Disadvantages:

- Adds interfaces and wiring compared with direct route logic
- Poorly chosen boundaries could produce pass-through layers
- Tests must avoid mocking away database guarantees

### Option C: Full domain-driven or hexagonal architecture

Create extensive ports, adapters, aggregates, commands, and domain abstractions around all infrastructure.

Advantages:

- Strong isolation from frameworks and infrastructure
- Useful for larger systems with multiple adapters and complex domains

Disadvantages:

- Adds concepts and files beyond the first release's needs
- Can hide the central reservation behavior behind ceremony
- Increases the amount the owner must learn before completing a vertical slice

## Decision

Choose **Option B** for the first portfolio release.

- FastAPI routes validate and translate HTTP input, call one application use case, and map results or domain failures to the API contract.
- Application services coordinate hold and reservation rules and own the transaction boundary for each use case.
- Repository interfaces expose only persistence operations required by those use cases.
- PostgreSQL repository implementations execute operations, including row locks, using the same transaction supplied to the application service.
- Time and identifier generation are injected where nondeterminism affects behavior.
- Domain failures do not depend on FastAPI response types.
- Additional abstraction is introduced only when a concrete second implementation or testing need justifies it.

Database constraints and concurrent integration tests remain authoritative for database invariants. Unit tests using substitutes do not replace those tests.

## Rationale

This structure demonstrates practical dependency boundaries while remaining small enough to explain from request to commit. Service-owned transactions align the atomic boundary with the complete business use case rather than with individual SQL calls.

## Consequences

- Route tests can focus on validation and HTTP mapping.
- Service tests can focus on domain decisions and coordination.
- Repository integration tests must cover SQL, migrations, locking, and constraints against PostgreSQL.
- Dependencies require explicit construction through FastAPI's dependency mechanism or a small application composition module.
- Pass-through layers with no meaningful responsibility should not be created.

## Validation

Before this decision is considered successfully implemented:

1. Hold and confirmation rules can be tested without starting an HTTP server.
2. HTTP contract tests verify request validation and domain-error mapping.
3. PostgreSQL integration tests verify row locking and uniqueness constraints through real repository implementations.
4. One trace through the code clearly identifies where HTTP mapping, business coordination, transaction ownership, and SQL occur.
5. A transaction rollback leaves no partial hold or reservation state.
6. The owner can explain why mocked repository tests cannot prove database concurrency guarantees.

## Revisit triggers

Reconsider this decision if:

- The application gains another delivery mechanism or persistence implementation.
- Domain complexity makes the service layer difficult to understand.
- Repositories become generic wrappers that obscure useful SQL behavior.
- Transaction ownership cannot be expressed cleanly at the use-case boundary.

## Owner review

Accepted by the project owner on 2026-09-11.

