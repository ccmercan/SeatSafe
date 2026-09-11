# Phase 1 evidence: retrieve an event-seat availability snapshot

- **Date:** 2026-09-11
- **Checkpoint status:** Implemented and locally verified

## Behavior delivered

`GET /v1/events/{event_id}/seats` returns a stable ordered list containing each event
seat's identifier, location, price, and current `available`, `held`, or `reserved`
status. A missing event returns the standard `resource_not_found` Problem Details
response. An existing event with no seats returns an empty list.

The application service calculates the public status from PostgreSQL facts and an
injected clock. An unexpired active hold reads as `held`; a hold at or before its
expiration boundary reads as `available`; and an active reservation takes precedence.
The read path intentionally does not lock a seat. Hold creation still performs the
authoritative lock and re-check.

A direct, test-only seed command resets the disposable `_test` database and inserts one
event with three seats and stable UUIDs. No HTTP reset endpoint was added.

## Requirement traceability

| Requirement | Evidence |
|---|---|
| FR-SEAT-001 | The API and PostgreSQL tests retrieve a seeded layout and computed availability. |
| FR-SEAT-003 | ADR-011 documents that reads are snapshots; hold creation remains authoritative. |
| QR-TEST-001 | The service uses an injected clock and fixed test identifiers. |
| QR-TEST-002 | The guarded seed command recreates the same disposable scenario on repeated runs. |
| QR-SEC-002 | Reset remains a direct database test utility guarded by `require_test_database`; no reset route exists. |

## Test placement

- Application tests prove status precedence and the exact expiration boundary without
  starting FastAPI or PostgreSQL.
- API tests prove the success schema and standardized missing-event failure.
- The PostgreSQL integration test runs the seed twice, inserts real hold/reservation
  records, and proves ordering and all three statuses through the SQL repository.
- A manual HTTP call proves the documented seed-to-endpoint workflow.

## Measured validation

Complete suite:

```text
28 passed, 2 warnings in 0.96s
```

Command:

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /private/tmp/seatsafe-venv/bin/python -m pytest -p pytest_asyncio.plugin -q
```

Static checks:

```text
All checks passed!
37 files formatted
```

Manual response check:

```text
GET /v1/events/00000000-0000-4000-8000-000000000020/seats -> 200 OK
3 ordered seats: Main A1, A2, A3
```

## Known limitations

- Availability is a point-in-time snapshot; callers must handle a later hold conflict.
- Seat ordering compares the stored seat number as text. That is deterministic for the
  seeded `1`–`3` layout, but natural numeric ordering must be designed before layouts
  contain values such as `2` and `10`.
- The seed command clears the entire disposable test database and therefore refuses any
  environment or database name that is not explicitly marked for testing.
- The two previously documented test-client dependency deprecation warnings remain.
- Reservation confirmation, idempotency, and a controlled simultaneous-request test
  remain Phase 1 work.
