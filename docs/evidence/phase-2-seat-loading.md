# Phase 2 evidence: seat-to-reservation client flow

- **Date:** 2026-09-22
- **Scope:** native seat-list loading, selection, hold creation, and reservation
  confirmation with stable retry behavior.

## Implemented

- Xcode project with iOS 17 deployment target and a shared `SeatSafe` scheme.
- SwiftUI seat list with loading, empty, transport-error, and result states.
- Local single-seat selection, visible selection summary, and non-selectable held/reserved
  rows.
- `@Observable @MainActor` model injected with an async `SeatService` protocol.
- URLSession service decoding the existing backend snapshot endpoint and stable demo event.
- HTTP hold service sends `POST /v1/holds` with the backend's required idempotency header.
- One pending seat/key pair is saved in UserDefaults before sending; transport errors and
  cancellation preserve it, and Retry sends the same values. Restored attempts remain
  retryable even when the newest seat snapshot says the seat is held.
- XCTest coverage for service result/error mapping, backend JSON decoding, selection,
  UserDefaults persistence, and ambiguous retry behavior.
- Local-network-only App Transport Security allowance for the local development API.
- Backend hold creation now requires a stable `Idempotency-Key`; same-key retries return
  the original successful response, while a key reused for another seat is rejected.
  Database changes and concurrency/rollback test evidence are documented in
  [ADR-014](../decisions/014-use-idempotency-for-hold-creation.md).
- Reservation confirmation sends the saved hold ID and `Idempotency-Key` to
  `POST /v1/reservations`. UserDefaults keeps the hold and key through an uncertain result;
  a recreated model can retry and get the original successful result. Definite expiration
  clears the unusable flow. The accepted persistence choice is in
  [ADR-016](../decisions/016-persist-pending-confirmation-locally.md).

## Validation

- Backend validation for the hold-idempotency foundation:
  from `backend/`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p pytest_asyncio.plugin -q`
  passed: **48 tests, 0 failures**. `ruff check src tests` and
  `ruff format --check src tests` passed. PostgreSQL integration cases include same-key
  concurrency, key mismatch, and atomic rollback.
- `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -project ios/SeatSafe.xcodeproj -scheme SeatSafe -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /private/tmp/seatsafe-derived test`
  passed after confirmation: **15 tests, 0 failures** on the iOS 26.4 Simulator. Tests cover
  request shape, restored retry using the same hold/key, and clearing a definitely expired
  confirmation. The backend was stopped, so an expected connection-refused message came
  only from the app launch attempt; all tests use stubbed or mocked services.
- `swift-format lint --strict ios/SeatSafe/SeatSafeApp.swift ios/SeatSafe/HoldCreation.swift ios/SeatSafeTests/SeatListModelTests.swift`
  passed using the repository's four-space `.swift-format` configuration.
- The installed simulator runtime is iOS 26.4. iOS 17 runtime compatibility remains
  unverified locally, as recorded in ADR-012.
- Phase 2 cancellation, stale-response, and repeated-action validation was added afterward;
  see [Phase 2 concurrency evidence](phase-2-concurrency.md) for the final 21-test result.

## Limitations

- The event ID and loopback API address are demo configuration, not user-selectable event
  discovery or production environment configuration.
- The local flow store is intentionally limited to one in-progress attempt, matching the
  current single-seat demo flow. The backend remains authoritative for availability.
- The screen-level confirmation journey is validated by the real-backend UI smoke test in
  [Phase 3 evidence](phase-3-ui-smoke.md).
