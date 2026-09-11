# ADR-004: Use disposable PostgreSQL test environments

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

SeatSafe integration tests must validate migrations, constraints, transactions, idempotency, and concurrent reservation attempts against PostgreSQL. Tests also need deterministic data and must not depend on execution order or manual database cleanup.

The reset mechanism is a security boundary. A convenient HTTP reset endpoint could accidentally become available outside a test environment, while a transaction-only test fixture cannot represent every concurrency scenario because independent connections must observe committed state.

## Options considered

### Option A: One disposable PostgreSQL instance per test session with direct reset-and-seed fixtures

Start an isolated PostgreSQL environment for the integration-test suite, apply production migrations, and use test-harness database fixtures to reset and seed scenario data between tests.

Advantages:

- Exercises the real PostgreSQL behavior and production migrations
- Supports separate connections for concurrency tests
- Keeps destructive reset controls outside the application API
- Provides a practical balance between isolation and feedback time

Disadvantages:

- Requires a local container runtime or equivalent PostgreSQL environment
- Reset logic must handle foreign keys and sequences correctly
- Tests within a session still share infrastructure and require disciplined isolation

### Option B: A separate database or schema for every test

Create an isolated database or schema, apply migrations, run one test, and dispose of it.

Advantages:

- Strong isolation
- Better foundation for parallel execution

Disadvantages:

- More orchestration and migration overhead
- Slower feedback for the initial project
- Parallel resource ownership is more complex to diagnose

### Option C: A test-only HTTP reset endpoint

Expose an endpoint that resets and seeds application data when test configuration is enabled.

Advantages:

- Convenient for tests that can interact only through HTTP
- Can express named end-to-end scenarios

Disadvantages:

- Creates a sensitive application capability
- Requires strong negative checks to prove it is unavailable in production
- Couples database integration tests to the API layer

## Decision

Choose **Option A** for Phase 1.

- The integration suite uses a disposable PostgreSQL instance created for the test session.
- The production migration path initializes the schema.
- Test-harness fixtures connect directly to that isolated database to reset and seed stable scenarios between tests.
- Concurrency tests use independent connections and real transaction boundaries rather than a single outer rollback transaction.
- Reset credentials and commands target only an explicitly identified test database.
- The application exposes no HTTP reset endpoint in Phase 1.

A protected scenario-control mechanism may be considered for XCUITest in Phase 3. That would require a separate decision covering configuration, authentication, deployment exclusion, and negative production checks.

## Rationale

This approach preserves the database fidelity required by the project's primary risk while keeping the initial workflow understandable. It avoids both a production security hazard and premature per-test database orchestration.

## Consequences

- Local integration testing requires access to PostgreSQL through the documented development environment.
- Reset and seed helpers are test infrastructure, not production service behavior.
- The suite must fail safely if its configured target is not unmistakably a test database.
- Tests that need committed visibility cannot rely exclusively on automatic transaction rollback fixtures.
- Parallel test execution is deferred until isolation ownership is designed and measured.

## Validation

Before this decision is considered successfully implemented:

1. A documented command starts a clean PostgreSQL test environment and applies production migrations.
2. Repeated test runs produce the same seeded identifiers and outcomes.
3. Changing test order does not change results.
4. A concurrency test uses separate connections and observes committed database behavior.
5. Reset logic refuses to target a database that is not explicitly configured as a test database.
6. Production configuration exposes no reset endpoint or reset command.

## Revisit triggers

Reconsider this decision if:

- Parallel execution becomes necessary to meet measured feedback-time goals.
- Shared session infrastructure causes isolation failures.
- UI automation requires named scenarios that cannot be established safely through existing setup tools.

## Owner review

Accepted by the project owner on 2026-09-11.

