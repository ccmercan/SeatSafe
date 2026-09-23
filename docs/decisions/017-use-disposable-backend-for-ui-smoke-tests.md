# ADR-017: Run the UI smoke test against a disposable backend

- **Status:** Accepted
- **Date:** 2026-09-22
- **Decision owners:** Project owner and implementation collaborator

## Context

Phase 3 needs a repeatable XCUITest for the critical seat-to-reservation journey. The
test must begin with known availability, exercise the same HTTP API used by the app, avoid
manual database edits, and leave no service running or persistent test data behind.

In plain language, the test should use a freshly set-up practice venue each time, talk to
the real SeatSafe server, then throw the practice setup away when it finishes.

ADR-004 keeps reset operations out of the application API. Its test-only seed command
already refuses to run unless configured for a database whose name ends in `_test`.

## Options considered

### Option A: Orchestrate the app with a disposable PostgreSQL database and real API

A host-side runner starts the pinned PostgreSQL container, applies production migrations,
seeds the known three-seat scenario with the guarded test command, starts the local API,
runs XCUITest, and tears the services down on success, failure, or interruption.

Advantages:

- Exercises the real screen, HTTP encoding/decoding, API behavior, and database state.
- Starts each run with the same seat availability and discards its data at teardown.
- Keeps destructive reset and seed controls outside the running application API.
- Reuses the disposable PostgreSQL approach already validated by backend tests.

Disadvantages:

- Requires Docker Desktop, Xcode, and a simulator; it is slower than an isolated UI test.
- The runner must manage process readiness, logs, and teardown carefully.
- One test uses a shared seat fixture and must not run in parallel with another test that
  mutates that same fixture.

### Option B: Stub the app's network responses in the UI-test process

Launch the app with a test-only service implementation or intercepted URLSession responses.

Advantages:

- Fast and deterministic without Docker or a running API.
- Easy to exercise difficult screen states and controlled error responses.

Disadvantages:

- Does not prove the real API and database work with the visible app journey.
- Adds a test-service injection seam to the app and still needs production-exclusion checks.

### Option C: Add a test-only HTTP reset/scenario endpoint

Let the UI test call the API to reset and seed its own database state.

Advantages:

- Convenient for choosing named scenarios from XCUITest.
- Keeps orchestration inside HTTP clients.

Disadvantages:

- Introduces a dangerous data-erasing capability into the server surface.
- Requires authentication, configuration safeguards, and negative tests proving it is
  absent from production.
- Duplicates the direct, guarded seed utility and weakens ADR-004's separation boundary.

## Decision

Choose **Option A** for the first XCUITest smoke journey.

- `tools/run-ios-ui-tests.sh` owns test setup and teardown. It refuses to take over an
  already-running SeatSafe test database or an API already bound to port 8000.
- The runner starts the existing Compose PostgreSQL service (temporary `tmpfs` data),
  applies migrations, runs the guarded deterministic demo seed, starts Uvicorn on
  `127.0.0.1:8000`, waits for `/health`, runs the Xcode test scheme, and stops the API and
  Compose service in a shell trap.
- The XCUITest target runs serially against the stable demo event and seat identifiers.
- Debug builds accept one launch argument that clears only the app's saved pending
  reservation flow before the test starts. The argument handling is compiled out of
  Release builds. The test validates clean start state; it does not expose a server reset
  endpoint.
- The initial smoke test covers seat selection, hold creation, reservation confirmation,
  and display of the returned reservation ID. More failure scenarios remain separate work.
- For the stale-availability conflict journey, XCUITest sends a competing hold request to the
  real API after the app loads seats and before the app submits its own hold. This models
  another client without adding scenario endpoints or changing the stable demo seed. Each
  journey uses a different seeded seat so one UI test cannot consume another's starting state.

## Rationale

The first UI smoke test should connect the main pieces once, because this project needs
evidence that its visible app and real backend cooperate. Lower-level tests remain faster
and more focused for individual failure cases. A disposable environment prevents this
realistic test from consuming or polluting manual demo data.

## Validation

1. The runner rejects an already-running managed database or a service already using the
   app's configured API port rather than resetting state it does not own.
2. The guarded seed command runs only against the configured test database.
3. A successful test visibly selects a seat, creates a hold, confirms it, and displays a
   syntactically valid reservation UUID.
4. Teardown stops Uvicorn and removes the temporary Compose database on both success and
   test failure.
5. The app's pending-flow reset argument has no effect in Release builds.
6. Two consecutive runner executions start from clean seat availability and pass without
   fixed-duration sleeps or automatic test retries.
7. A competing hold request receives HTTP 201; the app's subsequent request is rejected,
   displays the unavailable state, refreshes the seat to held, and disables its selection.

## Revisit triggers

- CI cannot provide Docker or a compatible disposable PostgreSQL service.
- A named error scenario cannot be constructed through the disposable host-side setup.
- Parallel UI execution is introduced and shared fixture ownership must change.
- A future authenticated test-control mechanism offers a safer, measured advantage over
  host-side orchestration.

## Owner review

Accepted by the project owner on 2026-09-22 as **Option A**.
