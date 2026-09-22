# ADR-007: Use database-backed idempotency for reservation confirmation

- **Status:** Accepted
- **Date:** 2026-09-11
- **Decision owners:** Project owner and implementation collaborator

## Context

A client may send a reservation-confirmation request, lose the response, and retry without knowing whether the first request succeeded. Repeated taps, client retry behavior, and concurrent delivery can create the same uncertainty.

In plain language, an idempotency key acts like a receipt number. If the server sees the same receipt number for the same purchase again, it returns the known result instead of making a second purchase.

The active-reservation uniqueness constraint prevents invalid duplicate rows, but it cannot by itself tell a retry that the earlier request succeeded or detect a key reused for different request data.

## Options considered

### Option A: Rely on the client to prevent retries

Disable the confirmation control while a request is running and trust the client to send the operation once.

Advantages:

- No server-side idempotency storage
- Reduces accidental duplicate taps in the normal UI

Disadvantages:

- Cannot prevent network, process, or client retries
- Does not solve an ambiguous lost response
- Other clients could omit the protection

### Option B: Rely only on the active-reservation constraint

Allow retries to reach normal confirmation logic and let the database reject a duplicate active reservation.

Advantages:

- Preserves the core no-duplicate invariant
- Requires no separate idempotency records

Disadvantages:

- A successful retry may receive a conflict rather than the original success
- Cannot distinguish a retry from a genuinely competing request
- Does not detect reuse of one key with different request data

### Option C: Store idempotency records in PostgreSQL

Associate each confirmation key with its operation scope, request fingerprint, and logical result.

Advantages:

- Replays a stable result for a completed retry
- Handles retries across application processes or restarts
- Detects accidental key reuse with different input
- Can be tested under simultaneous delivery

Disadvantages:

- Adds persistence and transaction logic
- Requires a retention policy in a production-scale system
- Concurrent first use of the same key must be coordinated correctly

## Decision

Choose **Option C** for reservation confirmation.

- The confirmation API is `POST /v1/reservations`. Its JSON body contains `hold_id`, and
  its HTTP `Idempotency-Key` header contains the stable key for the logical attempt.
- A missing, empty, or over-255-character key is a request-validation failure.
- The database uniquely scopes the key by owner identity and operation type.
- The record contains a stable fingerprint of the request fields that affect the operation.
- Repeating a completed request with the same key and fingerprint returns the original
  `201 Created` status and JSON response body. The API does not add a replay-only field,
  so the response contract remains identical.
- Reusing the key with a different fingerprint returns a defined client error and performs no new reservation operation.
- Concurrent requests using the same new key are coordinated by a database uniqueness constraint and transaction behavior.
- Creation of the reservation and completion of its idempotency record occur atomically: both commit or both roll back.
- The active-reservation constraint remains independent defense against competing requests that use different keys.

For Phase 1, the request fingerprint covers the `hold_id`, the only business input to
confirmation. If confirmation later gains additional fields that change its meaning,
those fields must be added to canonical fingerprint input and tests.

Before recording the key, PostgreSQL takes a transaction-scoped advisory lock for the
owner, operation, and idempotency key. This makes two simultaneous first uses of one key
wait for the first transaction's result, including when they name different holds. After
the key is clear, the service locks the relevant `EventSeat` row to serialize different
confirmation keys that target one seat. Both locks are released automatically at commit
or rollback.

For example, if Alice confirms hold `H1` using key `K1` and the response is lost, retrying `H1` with `K1` returns Alice's original reservation. Trying to confirm a different hold `H2` with `K1` is rejected because the receipt number was reused for a different operation.

The storage-retention policy is deferred because the first release uses a local deterministic environment. It must be defined before claiming production readiness.

## Rationale

Database-backed records give the client a stable answer after ambiguous delivery while remaining correct across restarts. They complement rather than replace seat-level locking and uniqueness constraints.

## Consequences

- Confirmation callers must generate and retain one stable key for all retries of a logical action.
- The key is sent in `Idempotency-Key`; the request body remains reservation data only.
- The server must canonicalize relevant request data before computing its fingerprint.
- Logs should include the idempotency key and correlation identifier without recording sensitive data.
- Service tests must cover same-key replay and changed-payload rejection.
- PostgreSQL integration tests must cover simultaneous use of the same key and different keys.
- A future production design must define expiration, cleanup, and storage limits for idempotency records.

## Validation

Before this decision is considered successfully implemented:

1. Repeating confirmation with the same key and request returns one logical reservation.
2. The database contains only one reservation and one completed idempotency record for that logical action.
3. Reusing a key with different request data returns the defined client error.
4. Simultaneous same-key requests cannot create duplicate work.
5. Simultaneous different-key requests for one seat still produce at most one active reservation.
6. A forced transaction failure leaves neither a partial reservation nor a completed idempotency result.
7. The owner can explain why idempotency and uniqueness solve different problems.
8. The owner can explain why the idempotency-key lock and seat-row lock protect different scopes.

## Revisit triggers

Reconsider this decision if:

- Idempotency data volume requires an explicit retention and archival strategy.
- Confirmation processing moves to asynchronous messaging.
- Owner identity or operation scope changes materially.

## Owner review

Accepted by the project owner on 2026-09-11.
