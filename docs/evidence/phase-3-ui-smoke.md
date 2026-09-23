# Phase 3 evidence: reservation UI journeys

- **Date:** 2026-09-23 (updated)
- **Scope:** four XCUITest journeys: three backed by the real local API and a disposable
  PostgreSQL database, plus one deliberate API-unavailable journey.

## Implemented

- Added the `SeatSafeUITests` target to the shared Xcode scheme.
- The UI test launches SeatSafe, selects the stable demo seat by accessibility identifier,
  creates a hold, confirms it, and checks that the reservation confirmation/ID is visible.
- A second UI test deliberately creates a stale-availability conflict: after SeatSafe loads
  and the user selects a free seat, the test sends a competing hold request to the real API.
  It verifies the app explains the conflict, refreshes the seat to `held`, and disables it.
- A third, isolated UI test creates a hold with the real API's configured 8-second duration,
  polls the seats endpoint until the server reports the hold expired, then tries to confirm.
  It verifies the API rejects confirmation, the app displays the expired state, and the seat
  is refreshed as available/selectable.
- A fourth, isolated UI test runs while the API is stopped. It verifies the app displays its
  recoverable seat-loading error, exposes the retry action to accessibility, and keeps the
  error visible when retry is attempted while the API remains unavailable. No fake error
  endpoint or test-only backend mode is used.
- The journeys use distinct seeded seats so one journey cannot consume another's
  starting state. No API reset endpoint or fixed sleep was added.
- `tools/run-ios-ui-tests.sh` verifies exclusive use of the app's API port and managed test
  database, starts the Compose PostgreSQL service, applies migrations, runs the guarded
  deterministic seed command, starts Uvicorn, and waits for its health endpoint.
- A shell trap stops the API and removes the temporary database/network whether Xcode
  succeeds or fails. The PostgreSQL data directory is `tmpfs` and no reset endpoint is
  added to the app API.
- The UI test passes a launch argument that clears only the saved reservation flow. Its
  handling is inside `#if DEBUG`, so the test-only control is omitted from Release builds.
- The first repeatability check found that this project did not define Swift's `DEBUG`
  compilation condition in its Debug app target. After adding it explicitly, later
  simulator diagnostics exposed a SwiftUI row hit-area issue. Giving each seat row a
  rectangular content shape made its full visible area selectable and independently
  testable.

## Validation

- After the compile-condition and row-hit-area fixes, `./tools/run-ios-ui-tests.sh` passed
  **twice consecutively** from fresh disposable databases on the iPhone 17 Pro simulator
  (iOS 26.4): **15 unit tests and 1 UI test, 0 failures per run**.
- On 2026-09-23, two consecutive executions of `./tools/run-ios-ui-tests.sh` passed on the
  iPhone 17 Pro simulator (iOS 26.4.1): **21 unit tests and 2 UI tests, 0 failures per run**.
  Result bundles: `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-20260923-112456.xcresult`
  and `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-20260923-112630.xcresult`.
- After adding expiry coverage, two more consecutive full executions passed on the same
  simulator: **21 unit tests + 2 normal-duration UI tests, then 1 isolated expiry UI test;
  0 failures in each execution**. The expiry-only run restarted the API with an 8-second
  hold duration and cold-booted the simulator between Xcode invocations. Result bundles:
  `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-20260923-114646.xcresult`,
  `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-expiration-20260923-114646.xcresult`,
  `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-20260923-114923.xcresult`,
  `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-expiration-20260923-114923.xcresult`.
- During implementation, the first combined run exposed that the happy-path test's booked seat
  could not also be the conflict test's initial fixture. The journeys now use separate seats.
  A result bundle also exposed that the existing five-second confirmation check ran before the
  UI published its hold-created state; the test now waits for that explicit state before
  continuing. No automatic retry was used.
- The runner removed the API process and disposable PostgreSQL container/network after each
  successful run.
- Both runs exercised the real service contract: the app loaded seats, posted a hold,
  posted a reservation confirmation, displayed the returned reservation identifier, and
  the runner removed the API/container afterward.
- Expiration also used the real server clock and real configured duration. The test waited for
  observable seat state instead of sleeping for a guessed interval; confirmation then proved
  the API's server-side expiration rule is authoritative.
- On 2026-09-23, the final runner passed **twice consecutively** on the iPhone 17 Pro simulator
  (iOS 26.4.1). Each run passed **21 unit tests + 2 normal UI tests + 1 isolated expiry UI test
  + 1 isolated unavailable-API UI test, with 0 failures**. Result bundles:
  `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-20260923-125233.xcresult`,
  `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-expiration-20260923-125233.xcresult`,
  `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-api-unavailable-20260923-125233.xcresult`,
  `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-20260923-125555.xcresult`,
  `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-expiration-20260923-125555.xcresult`,
  and `/var/folders/kd/z2xy9z1n6sx82j34p3xnbdqr0000gn/T/SeatSafe-UI-api-unavailable-20260923-125555.xcresult`.
- The unavailable-API test was first run in isolation and passed; the same test also passed as
  part of the full runner. A prior attempt revealed that the composed SwiftUI error view hid
  child accessibility identifiers. Moving the error identifier onto its description exposed
  the retry button correctly. A separate earlier full run showed that tapping only the seat
  title could miss the containing row action; the tests now tap the accessible row button.
- The Debug app bundle contains the UI-test reset argument; the Release app bundle does
  not. The Release configuration was built before checking its bundle strings.
- The test waits on accessibility elements and service state; it does not use fixed sleeps
  inside the UI test or automatic retries.
- A teardown hook adds a screenshot attachment to the Xcode result bundle when the test case
  has recorded a failure. Passing test cases do not add these failure screenshots.

## Limitations

- Happy path, stale-seat conflict, hold expiration, and API-unavailable/retry behavior are
  covered. Network failure during an in-flight write, offline recovery, accessibility-size,
  and localization journeys are not yet automated in XCUITest. Model-level tests cover
  ambiguous hold/confirmation retries and reuse of their idempotency keys.
- The locally available simulator uses iOS 26.4; minimum iOS 17 runtime compatibility is
  still unverified.
- Xcode result bundles are generated in the host temporary directory and their exact paths
  are printed by the runner. CI artifact retention is future Phase 4 work.

## Decisions and exit

The host-side disposable-backend setup and its alternatives are recorded in
[ADR-017](../decisions/017-use-disposable-backend-for-ui-smoke-tests.md). Hold-expiry test
acceleration is recorded in [ADR-018](../decisions/018-accelerate-expiry-in-ui-tests.md).

Phase 3 exit condition: met. The UI journeys run repeatedly without manual backend setup and
produce useful Xcode result bundles with test logs, failure screenshots, and accessibility
diagnostics. Phase 4 has not started.
