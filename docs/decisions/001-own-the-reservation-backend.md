# ADR-001: Own the reservation backend

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

SeatSafe needs event, seating, hold, and reservation data. The project could consume a real ticketing API, use a public event feed with simulated reservations, or own a small deterministic backend.

The portfolio goal is to demonstrate native application testing, API automation, database behavior, concurrency, CI, debugging, and testability. Tests must be repeatable locally and in CI.

## Options considered

### Option A: Commercial ticketing and seating API

Advantages:

- Real provider data and integration experience
- Less initial backend implementation

Disadvantages:

- Credentials, quotas, availability, and licensing constraints
- Mutable inventory makes tests nondeterministic
- Typically cannot reset data or create real reservation conflicts
- External failures can make CI untrustworthy
- Core database and concurrency behavior remains outside the project

### Option B: Public event API plus a local reservation layer

Advantages:

- Realistic event names and schedules
- Local control over reservation behavior
- Demonstrates an external-service adapter

Disadvantages:

- Still introduces network instability and changing data
- Creates two data ownership models before the core behavior is complete
- Adds mapping and caching complexity that does not initially strengthen the central quality story

### Option C: Local FastAPI reservation backend with deterministic seeded data

Advantages:

- Complete control over test data and failure scenarios
- Enables transaction, idempotency, expiration, and concurrency testing
- Demonstrates Python, API design, PostgreSQL, and service testability
- Reliable local and CI execution

Disadvantages:

- More software must be designed and maintained
- Event content is synthetic
- Production scaling characteristics can only be modeled, not proven

## Decision

Choose **Option C** for the first portfolio release. Build a small FastAPI service backed by PostgreSQL and populate it with deterministic fictional events and venue layouts.

Keep event discovery behind an interface so a read-only external event provider could be added later without changing reservation ownership. Do not add that integration until the core release criteria are satisfied.

## Rationale

Owning the backend exposes the most relevant engineering problems for the target roles: API testing, SQL integrity, race conditions, observability, deterministic automation, failure injection, and CI. It makes the test results attributable to code in this repository rather than to an uncontrolled third party.

## Consequences

- The repository owns event and reservation data for the initial release.
- Tests may seed and reset known data in isolated environments.
- The team must design database constraints and transaction behavior explicitly.
- The README must clearly state that the product does not access or sell real tickets.
- A future external event source must use an adapter and remain non-authoritative for reservations.

## Validation

Before this decision is considered successfully implemented:

1. A clean environment can be seeded with the same stable scenario repeatedly.
2. API tests can reset their state without manual intervention.
3. Concurrent requests for one seat produce at most one active reservation.
4. CI can execute without credentials for a commercial ticketing provider.
5. The owner can explain the alternatives, tradeoffs, and revisit conditions.

## Revisit triggers

Reconsider this decision only if:

- A target role specifically requires third-party API integration evidence.
- The core deterministic system and quality gates are complete.
- A suitable provider offers a stable sandbox with resettable test data.

## Owner review

Accepted by the project owner on 2026-09-11.

The acceptance was based on these conclusions:

1. The deterministic-testing benefit justifies building and maintaining the backend.
2. Real event data is deferred until after the first portfolio release.
3. FastAPI is included in this decision as the initial backend framework rather than requiring a separate framework-selection ADR.
