# ADR-018: Accelerate hold expiry in the isolated UI test run

- **Status:** Accepted
- **Date:** 2026-09-23
- **Decision owners:** Project owner and implementation collaborator

## Context

Phase 3 needs a screen-level test proving that a user cannot confirm a hold after it expires.
The real API uses its server clock to decide expiry. Its configured hold duration defaults to
300 seconds, and the app does not automatically remove the Confirm action when that server-side
deadline passes; it learns the hold expired when confirmation is attempted.

The test should exercise that real behavior without waiting five minutes, depending on timing
luck, or creating a test-only data-erasing API.

## Options considered

### Option A: Wait for the default five-minute hold to expire

Advantages:

- Uses the normal local API configuration with no special test setup.
- Exercises the actual expiry boundary end to end.

Disadvantages:

- Adds at least five minutes to a single UI scenario and slows local feedback.
- A longer test increases the chance that unrelated simulator issues interrupt the run.

### Option B: Run only the expiry journey against the real API with a short configured hold

Restart the API inside the disposable test runner with a short
`SEATSAFE_HOLD_DURATION_SECONDS` value, reseed the disposable database, then run only the
expiry XCUITest. The test waits until the real seat-read API reports the seat available before
asking the app to confirm the hold. Other UI journeys use the normal configured duration.

Advantages:

- Uses the production API, database, server clock, and app confirmation flow.
- Uses an existing bounded server setting instead of adding a reset endpoint or clock-control
  feature.
- Waits for an observable server state transition rather than a fixed-duration sleep.
- Keeps the normal happy-path tests isolated from the short expiry duration.

Disadvantages:

- The host runner must restart the API and invoke Xcode a second time for this one journey.
- The expiry test takes several seconds while the configured hold reaches its deadline.

### Option C: Add a test-only clock control or expiry endpoint

Advantages:

- Can make expiry immediate and directly controlled by the test.

Disadvantages:

- Adds a privileged test control to the server surface or more clock-injection wiring.
- Requires additional safeguards and proof that the control cannot be enabled in production.
- Expands the test architecture despite an existing configurable duration.

## Decision

Choose **Option B**.

- Keep the normal UI suite on the default 300-second hold duration.
- Restart the API for the expiration-only test using a short duration (8 seconds) and reseed
  only the disposable test database.
- The UI test creates a hold through the app, waits until `GET /v1/events/{id}/seats` reports
  that seat as `available`, then confirms through the app and verifies the expired explanation
  and refreshed availability.
- Do not add an expiration/reset route or an API clock-advancement control.

## Validation

1. Normal critical and conflict UI journeys pass with the default duration.
2. The isolated expiry UI journey obtains a hold, observes the API transition to available,
   receives the app's expired state after confirmation, and confirms the seat is selectable.
3. Two consecutive full runner executions pass with unit/UI counts recorded in Phase 3 evidence.
4. The runner removes its API process and disposable PostgreSQL container/network after success
   and failure.

## Revisit triggers

- UI tests need parallel execution and the shared disposable database must be partitioned.
- The API duration setting is removed or cannot safely be used for the isolated expiry run.
- The app gains server-driven expiry updates that make confirmation-based expiry a different
  user journey.

## Owner review

Accepted by the project owner on 2026-09-23 as **Option B**.
