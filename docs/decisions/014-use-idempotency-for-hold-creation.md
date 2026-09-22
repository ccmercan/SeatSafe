# ADR-014: Use database-backed idempotency for hold creation

- **Status:** Accepted
- **Date:** 2026-09-22
- **Decision owners:** Project owner and implementation collaborator

## Context

The iOS client can send `POST /v1/holds`, the server can create a hold, and the response
can be lost before the client receives the hold ID. If the client submits an ordinary new
request, the backend sees the already-active hold and returns a conflict; the client still
does not know the hold ID it needs to continue.

In plain language, a seat hold is like checking out a library book for a short time. If
the checkout succeeded but the receipt got lost, the same receipt number should let the
borrower retrieve that same checkout—not check the book out again or be told only that it
is already gone.

## Options considered

### Option A: Require a stable idempotency key for hold creation

Save the successful response in PostgreSQL under the owner, operation, and key. A retry
with the same key and request returns the saved response.

Advantages:

- Recovers the original hold ID and expiry after a lost response.
- Works across API processes and restarts.
- Detects reusing one key for a different seat.
- Matches the existing reservation-confirmation retry contract.

Disadvantages:

- Requires durable storage, transaction, and concurrency-control behavior.
- The client must retain the same key and request for the complete logical attempt.
- Production deployment needs an idempotency-record retention policy.

### Option B: Add an endpoint to look up the current user's hold

The client asks for its active hold after a timeout.

Advantages:

- Can reconcile without retaining the original response body.

Disadvantages:

- Adds another API contract and careful ownership-sensitive lookup behavior.
- Requires deciding what happens if the hold expired before reconciliation.

### Option C: Do not retry an uncertain request

Tell the user the outcome is unknown and wait for the hold to expire.

Advantages:

- Smallest backend change.

Disadvantages:

- Leaves a successful hold inaccessible to the client until expiry.
- Creates a poor recovery path and does not satisfy the retry requirement.

## Decision

Choose **Option A**. `POST /v1/holds` requires an `Idempotency-Key` header containing
1–255 characters. The request body remains `{ "event_seat_id": UUID }`.

- The key is scoped by the configured owner identity and operation `create_hold`.
- The request fingerprint is a canonical SHA-256 hash of `event_seat_id`.
- The database stores only successful hold outcomes. A rejected request does not reserve
  the key, so a later valid attempt may use it.
- Repeating the same key and seat returns the original `201` response status and body,
  including the original hold ID and expiry—even if the hold later expires.
- Reusing a key for a different seat returns `409 idempotency_key_reused` and creates no
  hold.
- The idempotency-key advisory lock is acquired before the event-seat row lock. Requests
  with the same key serialize; different keys for one seat still serialize on its row.
- The hold row and its idempotency response record commit or roll back together.
- Extend the existing `idempotency_records` table with nullable `hold_id` and
  `reservation_id` references and a database check that exactly one matching outcome is
  present for each operation.

## Rationale

The client needs the original hold identifier to confirm or release a hold. Replaying the
server's saved response is the smallest reliable recovery mechanism consistent with
ADR-007. The database row lock continues to arbitrate different logical attempts that
compete for the same seat; idempotency does not replace seat concurrency protection.

## Consequences

- Hold callers must generate one key per new logical attempt and retain it with the
  unchanged seat ID for every retry of that attempt.
- The API reports missing, empty, or overlong keys as request validation errors.
- A successful replay does not extend the hold duration.
- The client must show an uncertain state after a transport failure and retry using the
  same key; it must not silently make a new attempt with a fresh key.
- Hold and confirmation records share the table but retain typed foreign-key outcomes.
- Retention and cleanup of idempotency records remain a pre-production decision, as in
  ADR-007.

## Validation

1. A same-key/same-seat retry returns the original byte-stable `201` body.
2. A same-key/different-seat attempt returns `409 idempotency_key_reused`.
3. A missing, empty, or overlong key fails request validation.
4. Simultaneous same-key requests create one hold and one idempotency record.
5. Different keys competing for one seat still produce at most one active hold.
6. A forced idempotency-record database failure rolls back the hold.
7. Reservation-confirmation idempotency continues to work after the schema migration.
8. The iOS client retries a simulated lost response with the exact same key and seat ID.

## Revisit triggers

Reconsider this choice if authentication, hold ownership, expiry policy, or idempotency
retention changes materially.

## Owner review

Accepted by the project owner on 2026-09-22 as **Option A** for hold creation and
**Option 1** to extend the existing idempotency table with typed hold/reservation foreign
keys.
