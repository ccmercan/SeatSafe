# Phase 2 evidence: seat-snapshot loading foundation

- **Date:** 2026-09-22
- **Scope:** native seat-list loading and local seat selection; no reservation writes yet.

## Implemented

- Xcode project with iOS 17 deployment target and a shared `SeatSafe` scheme.
- SwiftUI seat list with loading, empty, transport-error, and result states.
- Local single-seat selection, visible selection summary, and non-selectable held/reserved
  rows; the interface clearly says selection has not created a hold.
- `@Observable @MainActor` model injected with an async `SeatService` protocol.
- URLSession service decoding the existing backend snapshot endpoint and stable demo event.
- XCTest coverage for service result/error mapping, backend JSON decoding, and selection.
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
- `xcodebuild ... build-for-testing` completed successfully for the generic iOS Simulator
  destination. This compiles both the app and XCTest target; it does not execute tests.
- An app build for the installed simulator SDK completed successfully before the plist
  was made explicit; the final `build-for-testing` also compiled the app with that plist.
- `xcodebuild -project ios/SeatSafe.xcodeproj -scheme SeatSafe -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/seatsafe-derived test`
  passed: **5 tests, 0 failures** on the iOS 26.4 Simulator.
- The installed simulator runtime is iOS 26.4. iOS 17 runtime compatibility remains
  unverified locally, as recorded in ADR-012.

## Limitations

- The event ID and loopback API address are demo configuration, not user-selectable event
  discovery or production environment configuration.
- The iOS hold action is not yet wired. Its pending key-storage/recovery lifecycle needs
  an explicit decision; selected seat remains local UI state, and the backend remains
  authoritative for availability.
