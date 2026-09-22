# Phase 1 evidence: confirm a reservation safely under retries

- **Date:** 2026-09-22
- **Checkpoint status:** Implemented and locally validated against PostgreSQL

## Behavior delivered

`POST /v1/reservations` accepts a `hold_id` in its JSON body and a stable
`Idempotency-Key` HTTP header. It checks for a saved result first. If a matching key and
request fingerprint already exist, it returns the saved status and original JSON body.
If the key exists for different request data, it returns `409 idempotency_key_reused`.

For a new request, PostgreSQL serializes first use of the owner-scoped idempotency key
with a transaction-scoped advisory lock. The service then locks the hold's `EventSeat`
row and re-reads the hold before checking its owner, active state, and expiry. It changes
the hold to `confirmed`, inserts one active reservation, stores the idempotency result,
and commits all changes together.

An expired hold is persisted as `expired` and returns `409 hold_expired`. A hold owned by
another configured user returns `403 hold_owner_mismatch`; a missing hold returns
`404 resource_not_found`. Missing or invalid idempotency headers use the standard
`422 validation_failed` response.

## Requirement traceability

| Requirement | Evidence |
|---|---|
| FR-RES-001 | Confirmation service changes a valid active hold into one active reservation. |
| FR-RES-002 | The same owner, key, and hold fingerprint replays the original response. |
| FR-RES-003 | The event-seat row lock and active-reservation partial unique index protect the seat. |
| FR-HOLD-003 | The confirmation service rejects a hold whose owner differs from the injected current user. |
| QR-TEST-001 | Fixed clock, identifiers, and explicit fake outcomes make service tests deterministic. |
| QR-TEST-007 | Tests assert returned state and persisted rows rather than scheduler order. |

## Test placement

- Application tests cover successful transition, same-key replay, changed-input key reuse,
  wrong owner, expiration at the exact deadline, inactive holds, and already reserved seats.
- API tests cover the request/response contract, required header, and standard key-reuse
  problem response.
- PostgreSQL integration tests use independent sessions to check simultaneous same-key
  replay and different-key attempts to confirm the same hold.

## Measured validation

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest_asyncio.plugin -ra` from
`backend/` completed with **39 passed** in 1.09 seconds against the disposable PostgreSQL
container. The two concurrency tests used independent service instances and database
sessions: one verified same-key replay creates one reservation and one stored result;
the other verified different keys cannot confirm the same hold twice. Pytest reported two
dependency deprecation warnings from Starlette's test client integration; they did not
fail the suite.

## Known limitations

- The API uses one server-configured demo user; it does not implement production
  authentication.
- The idempotency retention and cleanup policy is deferred until production-readiness
  work.
- Advisory locking uses PostgreSQL `hashtextextended`; a rare 64-bit hash collision can
  serialize unrelated keys but cannot merge their stored records or change correctness.
- Same-key serialization and seat serialization are separate: the idempotency lock
  protects one logical request key, while the seat row lock protects inventory state.
- A controlled test of two independently created holds racing for the same seat and a
  forced rollback after partial in-transaction work remain to be added.
