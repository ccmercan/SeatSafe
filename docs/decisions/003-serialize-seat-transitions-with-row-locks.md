# ADR-003: Serialize seat transitions with row locks and constraints

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

SeatSafe must preserve the invariant that one event seat cannot have multiple active reservations. Application code that reads availability and then writes a hold or reservation is vulnerable to a race: two transactions can observe the same available state before either writes.

The first release uses one PostgreSQL database and prioritizes a correctness strategy that is deterministic, observable, and explainable in automated tests.

## Options considered

### Option A: Application-level availability checks

Read availability in Python and write only when the seat appears available.

Advantages:

- Minimal database-specific logic
- Simple in a single-request demonstration

Disadvantages:

- A check followed by a write is not atomic
- Concurrent requests can both observe availability
- Correctness depends on request timing

### Option B: Optimistic concurrency

Store a version on the authoritative seat record and update only when the expected version still matches.

Advantages:

- Avoids holding a row lock while application work runs
- Works well when conflicts are uncommon

Disadvantages:

- Requires explicit conflict and retry behavior
- Adds version-management complexity to the first slice
- The database still needs constraints as final protection

### Option C: PostgreSQL row locking backed by uniqueness constraints

Lock the authoritative `EventSeat` row before evaluating and changing hold or reservation state. Retain database constraints that prevent invalid committed states.

Advantages:

- Serializes competing transitions for one seat
- Keeps the critical transaction straightforward to reason about
- Produces a clear losing request rather than a duplicate reservation
- Can be proven against real PostgreSQL with concurrent integration tests

Disadvantages:

- Contending requests wait for the same row
- Transactions must remain short and acquire locks consistently
- Incorrect lock ordering could create deadlocks as workflows grow

## Decision

Choose **Option C** for the first portfolio release.

- Each hold or confirmation transaction locks the relevant `EventSeat` row with PostgreSQL row-level locking before evaluating eligibility.
- The transaction performs only the database work required for the transition; no network calls or slow external work occur while the lock is held.
- Competing code paths acquire seat locks in a consistent order if multi-seat behavior is introduced later.
- A database uniqueness constraint or partial unique index prevents more than one active reservation for an event seat.
- Active-hold state uses a time-independent database status. Expiration is evaluated using the injected application clock while the row is locked, and an expired hold is transitioned before a replacement hold is created. A partial index will not depend on the database's current time.
- Python maps the losing transaction to a defined conflict response, but Python checks are not the final correctness boundary.

The exact columns, migration tooling, and repository interfaces will be specified during the Phase 1 schema design without changing this concurrency decision.

## Rationale

Row locking exposes the database-concurrency concept clearly and makes the first slice easier to defend than an optimistic retry protocol. Database constraints provide defense in depth if a future code path omits the expected lock.

## Consequences

- Hold and confirmation operations require explicit transaction boundaries.
- Integration tests must run against PostgreSQL; an in-memory substitute cannot validate the guarantee.
- Lock duration and acquisition order become review concerns.
- Expected contention produces a domain conflict, while deadlocks and unexpected database errors remain operational failures.
- Performance conclusions will be based on later measurement rather than assumed from the locking strategy.

## Validation

Before this decision is considered successfully implemented:

1. A controlled integration test starts simultaneous attempts for one available seat.
2. Exactly one attempt succeeds and losing attempts receive the defined conflict result.
3. The database contains at most one active reservation for the event seat.
4. Repeated confirmation with one idempotency key returns the same logical result rather than creating a duplicate.
5. Transaction logs or test evidence make the competing outcomes diagnosable.
6. The owner can explain why an application-level availability check alone is unsafe.

## Revisit triggers

Reconsider the strategy if:

- Measured contention makes lock waiting unacceptable.
- Multi-seat atomic reservations introduce significant lock-ordering complexity.
- The system is redesigned around multiple databases or regions where one PostgreSQL lock cannot protect the invariant.

## Owner review

Accepted by the project owner on 2026-09-11.

