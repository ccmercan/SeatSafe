# SeatSafe backend

This directory contains the FastAPI and PostgreSQL reservation service.

## Foundation checkpoint

The current scaffold provides:

- Application configuration through `SEATSAFE_` environment variables
- An injectable server-configured demo identity
- Correlation identifiers on responses
- RFC 9457-style Problem Details responses with stable SeatSafe codes
- A process-health endpoint at `GET /health`
- A hold-creation endpoint at `POST /v1/holds`
- A reservation-confirmation endpoint at `POST /v1/reservations` with database-backed
  idempotent retries
- A service-owned transaction that locks the event-seat row
- Expired-hold replacement and active-hold or reservation rejection
- Focused API, application, unit, and PostgreSQL integration tests

Reservation confirmation and event-seat retrieval are the next part of the Phase 1 vertical slice. PostgreSQL integration tests must use PostgreSQL; SQLite is not an accepted substitute for row-locking evidence.

## Start the disposable PostgreSQL service

Docker Desktop must be installed and running. From the repository root:

```bash
docker compose -f infrastructure/compose.test.yaml up -d --wait
```

The container exposes PostgreSQL only on local address `127.0.0.1`, port `54329`. Its data directory uses `tmpfs`, which means the test data lives in memory and disappears when the container is removed.

Inspect its state and logs:

```bash
docker compose -f infrastructure/compose.test.yaml ps
docker compose -f infrastructure/compose.test.yaml logs postgres
```

Remove the disposable environment:

```bash
docker compose -f infrastructure/compose.test.yaml down
```

The current image is pinned by both the official-image tag `postgres:17.11-alpine3.24` and its resolved multi-platform digest. This prevents a later image update from silently changing the test environment.

## Run the checks

Create the project-local Python environment once:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

If this repository is managed by a cloud file provider, mark the folder as **Keep Downloaded** before creating `.venv`. A dataless virtual environment can pause on every Python import. Alternatively, create the virtual environment in a local, non-synced directory.

Run unit and API tests without PostgreSQL:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p pytest_asyncio.plugin -m "not integration"
```

With the PostgreSQL container running, execute the complete suite:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p pytest_asyncio.plugin
```

Disabling automatic discovery prevents unrelated globally installed pytest plugins from changing the project's test environment. SeatSafe's async plugin is loaded explicitly.

## Create a hold

`POST /v1/holds` accepts an event-seat identifier and a client-generated
`Idempotency-Key` header (1–255 characters). Keep the same key for retries of the same
seat-hold attempt; use a new key for a new attempt.

```json
{
  "event_seat_id": "00000000-0000-4000-8000-000000000040"
}
```

Example request:

```bash
curl --request POST http://127.0.0.1:8000/v1/holds \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: demo-hold-attempt-001' \
  --data '{"event_seat_id":"00000000-0000-4000-8000-000000000040"}'
```

A successful request returns `201 Created` with the hold ID, active status, and expiration time. Missing seats return `resource_not_found`; seats with active holds or reservations return `seat_unavailable` using the Problem Details contract.
Repeating the same key and seat returns the original successful response, including its
original expiry time. Reusing that key for a different seat returns
`409 idempotency_key_reused`; unsuccessful requests do not reserve the key. See
[ADR-014](../docs/decisions/014-use-idempotency-for-hold-creation.md) for the decision
and concurrency/transaction details.

After applying the migration, replace the disposable database contents with the stable
manual-demo scenario:

```bash
SEATSAFE_ENVIRONMENT=test .venv/bin/python -m seatsafe.db.demo_seed
```

The command deliberately requires both `environment=test` and a database name ending
in `_test`. It refuses other targets because it clears existing rows before inserting
the stable scenario. The seeded identifiers are:

```text
event:      00000000-0000-4000-8000-000000000020
event seat: 00000000-0000-4000-8000-000000000040
event seat: 00000000-0000-4000-8000-000000000041
event seat: 00000000-0000-4000-8000-000000000042
```

Retrieve the ordered availability snapshot:

```bash
curl http://127.0.0.1:8000/v1/events/00000000-0000-4000-8000-000000000020/seats
```

This response is a snapshot, not a reservation. Another request may claim a seat after
it is read, so `POST /v1/holds` still locks the event-seat row and re-checks availability.

Confirm a hold using a client-generated key that remains stable for retries of this
confirmation attempt:

```bash
curl --request POST http://127.0.0.1:8000/v1/reservations \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: demo-confirmation-001' \
  --data '{"hold_id":"00000000-0000-4000-8000-000000000050"}'
```

The first successful request returns `201 Created`. Retrying the same `hold_id` with
the same key returns the original `201` response body. Reusing the key for a different
hold returns `409 idempotency_key_reused`. A hold that is expired or belongs to another
demo identity cannot be confirmed.

Once the project dependencies are installed, run the API with:

```bash
python3 -m uvicorn seatsafe.main:app --app-dir src --reload
```

Then request `http://127.0.0.1:8000/health`.

## Authentication limitation

Phase 1 does not implement production authentication. The server injects one configured demo-user identity. Tests can replace that dependency to verify ownership behavior. A client-provided user ID is not treated as trusted identity.
