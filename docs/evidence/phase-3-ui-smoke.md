# Phase 3 evidence: real-backend reservation UI smoke test

- **Date:** 2026-09-22
- **Scope:** one XCUITest happy-path journey backed by the real local API and a disposable
  PostgreSQL database.

## Implemented

- Added the `SeatSafeUITests` target to the shared Xcode scheme.
- The UI test launches SeatSafe, selects the stable demo seat by accessibility identifier,
  creates a hold, confirms it, and checks that the reservation confirmation/ID is visible.
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
- Both runs exercised the real service contract: the app loaded seats, posted a hold,
  posted a reservation confirmation, displayed the returned reservation identifier, and
  the runner removed the API/container afterward.
- The Debug app bundle contains the UI-test reset argument; the Release app bundle does
  not. The Release configuration was built before checking its bundle strings.
- The test waits on accessibility elements and service state; it does not use fixed sleeps
  inside the UI test or automatic retries.

## Limitations

- This is one happy-path smoke journey. Conflict, expiration, network failure, offline,
  accessibility-size, and localization journeys are not yet automated in XCUITest.
- The locally available simulator uses iOS 26.4; minimum iOS 17 runtime compatibility is
  still unverified.
- Xcode result bundles are generated in the host temporary directory and their exact paths
  are printed by the runner. CI artifact retention is future Phase 4 work.

## Decision

The host-side disposable-backend setup and its alternatives are recorded in
[ADR-017](../decisions/017-use-disposable-backend-for-ui-smoke-tests.md).
