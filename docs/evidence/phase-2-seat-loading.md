# Phase 2 evidence: seat-snapshot loading foundation

- **Date:** 2026-09-22
- **Scope:** native seat-list loading, local seat selection, and temporary hold creation;
  reservation confirmation is not yet wired in the iOS client.

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

## Validation

- Backend validation for the hold-idempotency foundation:
  from `backend/`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest -p pytest_asyncio.plugin -q`
  passed: **48 tests, 0 failures**. `ruff check src tests` and
  `ruff format --check src tests` passed. PostgreSQL integration cases include same-key
  concurrency, key mismatch, and atomic rollback.
- `xcodebuild -project ios/SeatSafe.xcodeproj -scheme SeatSafe -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/seatsafe-derived test`
  passed after this slice: **11 tests, 0 failures** on the iOS 26.4 Simulator.
- `swift-format lint --strict ios/SeatSafe/SeatSafeApp.swift ios/SeatSafe/HoldCreation.swift ios/SeatSafeTests/SeatListModelTests.swift`
  passed using the repository's four-space `.swift-format` configuration.
- The installed simulator runtime is iOS 26.4. iOS 17 runtime compatibility remains
  unverified locally, as recorded in ADR-012.

## Limitations

- The event ID and loopback API address are demo configuration, not user-selectable event
  discovery or production environment configuration.
- iOS confirmation is not yet wired; after a successful hold, the app currently shows the
  returned hold ID and expiry. The pending-attempt store is intentionally limited to one
  attempt, matching the current single-seat demo flow. The backend remains authoritative
  for availability.
