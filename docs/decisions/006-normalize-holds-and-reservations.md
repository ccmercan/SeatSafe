# ADR-006: Model holds and reservations as separate records

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

An event seat has a stable identity, but holds and reservations happen over time. SeatSafe needs to answer both "What is true now?" and "What happened before?" without storing conflicting copies of the same state.

In plain language, the seat is the thing being booked. A hold is a temporary claim on that seat. A reservation is the confirmed result. They are related, but they are not the same thing and do not have the same lifecycle.

## Options considered

### Option A: Store all current state on `EventSeat`

Add columns such as `status`, `held_by`, `hold_expires_at`, and `reserved_by` directly to the event-seat row.

Advantages:

- The current state is easy to read from one row.
- The first prototype requires fewer tables.

Disadvantages:

- Temporary hold data and permanent seat identity become mixed together.
- Releasing or replacing a hold overwrites useful history.
- Several nullable columns can represent contradictory combinations.
- Cancellation and repeated reservations become harder to audit.

### Option B: Store holds and reservations as normalized records

Keep `EventSeat` as the stable seat-at-an-event record. Store each hold in `SeatHold` and each confirmed booking in `Reservation`, with explicit statuses and timestamps.

Advantages:

- Each table represents one concept.
- Hold expiration, release, confirmation, and reservation cancellation remain visible.
- Database constraints can prevent multiple active records.
- Tests can verify both current behavior and lifecycle history.

Disadvantages:

- Availability requires examining related records instead of one status column.
- Transitions require careful transactions so related rows remain consistent.
- Status values and allowed transitions must be defined explicitly.

### Option C: Rebuild state from an event log

Store only events such as `HoldCreated`, `HoldExpired`, and `ReservationConfirmed`, then reconstruct the current state from the history.

Advantages:

- Complete audit history
- Flexible historical analysis

Disadvantages:

- Considerably more code and operational complexity
- Requires event ordering, replay, and projection design
- Does not strengthen the first portfolio slice enough to justify its cost

## Decision

Choose **Option B** for the first portfolio release.

- `EventSeat` identifies one physical seat at one event and is the row locked during competing transitions.
- `SeatHold` records the owner, status, creation time, and expiration time of a temporary claim.
- `Reservation` records the owner, status, confirmation time, and optional cancellation time.
- `IdempotencyRecord` associates a request key with its logical outcome so a safe retry does not create a second reservation.
- Fixed-status partial unique indexes prevent more than one active hold and more than one active reservation for an event seat.
- A unique relationship ensures one hold cannot produce multiple reservations.
- Expiration is evaluated while the `EventSeat` row is locked. Database indexes do not use the changing current time as a predicate.

For example, when Alice's hold expires, its row remains as history but changes from `active` to `expired`. Bob can then receive a new active hold. The database can distinguish the old historical hold from the one that currently controls the seat.

The exact column types, names, and status constraints will be finalized in the migration design while preserving this model.

## Rationale

Separate records make the lifecycle understandable without introducing event sourcing. The approach works with ADR-003: the service locks the stable `EventSeat` row, examines active related records, and changes them in one transaction. Partial unique indexes remain a final database safeguard.

## Consequences

- Queries must deliberately distinguish active records from historical records.
- Status transitions become domain behavior and require tests.
- Timestamps should use timezone-aware storage.
- Cancellation changes reservation state instead of deleting its history.
- Tests must cover invalid status combinations and transitions.
- Audit events may still be added for diagnostics, but they are not the source of truth.

## Validation

Before this decision is considered successfully implemented:

1. Migrations create the relationships and uniqueness constraints.
2. An expired hold remains in history and no longer blocks a replacement hold.
3. One hold cannot produce two reservations.
4. One event seat cannot have two active holds or two active reservations.
5. Cancelling a reservation preserves its record and permits the defined next state.
6. The owner can describe the difference between a seat, a hold, and a reservation.

## Revisit triggers

Reconsider this decision if:

- Historical state is not useful enough to justify the additional joins.
- Audit or regulatory requirements make an append-only event model necessary.
- Measured query behavior requires a separate current-state projection.

## Owner review

Accepted by the project owner on 2026-09-11.

