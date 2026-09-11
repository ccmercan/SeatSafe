# Phase 1 evidence: create one seat hold

- **Date:** 2026-09-11
- **Checkpoint status:** Implemented and locally verified

## Behavior delivered

`POST /v1/holds` creates a temporary active hold for an existing available event seat. The application service owns the transaction, the PostgreSQL repository locks the authoritative event-seat row, and the database prevents multiple active holds.

An active reservation or unexpired hold produces the stable `seat_unavailable` problem. A hold whose expiration time is equal to or earlier than the injected clock is changed to `expired` before the replacement hold is created.

## Requirement traceability

| Requirement | Evidence |
|---|---|
| FR-SEAT-003 | Hold repository locks and evaluates server-owned event-seat state. |
| FR-HOLD-001 | Service creates a hold using the configured duration and injected clock. |
| FR-HOLD-002 | Service rejection plus PostgreSQL partial unique index protect the one-active-hold invariant. |
| QR-TEST-001 | Fixed time and identifiers make application tests deterministic. |
| QR-TEST-007 | Tests assert transitions and results without depending on scheduler timing. |

## Test placement

- Application tests prove decision order, expiration boundaries, output, and transaction commit behavior with explicit fakes.
- API tests prove the `201` contract and `409` Problem Details mapping.
- PostgreSQL integration tests prove migration creation, the partial unique index, and real repository behavior.

## Measured validation

```text
19 passed, 2 warnings in 0.71s
```

Command:

```bash
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /private/tmp/seatsafe-venv/bin/python -m pytest -p pytest_asyncio.plugin -q
```

Static checks:

```text
All checks passed!
29 files formatted
```

## Known limitations

- The database does not yet have a reusable deterministic seed command for manual API demonstrations.
- The test client emits two dependency deprecation warnings. They do not change the result, but dependency compatibility must be resolved before warnings become a CI gate.
- The completed tests prove sequential conflicts and the database constraint. A controlled simultaneous-request test is still required to validate lock waiting and winner/loser behavior.
- Reservation confirmation and idempotency are not implemented yet.
