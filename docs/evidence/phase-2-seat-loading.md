# Phase 2 evidence: seat-snapshot loading foundation

- **Date:** 2026-09-22
- **Scope:** first native client slice only; no seat selection or reservation writes yet.

## Implemented

- Xcode project with iOS 17 deployment target and a shared `SeatSafe` scheme.
- SwiftUI seat list with loading, empty, transport-error, and result states.
- `@Observable @MainActor` model injected with an async `SeatService` protocol.
- URLSession service decoding the existing backend snapshot endpoint and stable demo event.
- XCTest source covering service result/error mapping and backend JSON decoding.
- Local-network-only App Transport Security allowance for the local development API.

## Validation

- `xcodebuild ... build-for-testing` completed successfully for the generic iOS Simulator
  destination. This compiles both the app and XCTest target; it does not execute tests.
- An app build for the installed simulator SDK completed successfully before the plist
  was made explicit; the final `build-for-testing` also compiled the app with that plist.
- `xcodebuild -project ios/SeatSafe.xcodeproj -scheme SeatSafe -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -derivedDataPath /tmp/seatsafe-derived test`
  passed: **3 tests, 0 failures** on the iOS 26.4 Simulator.
- The installed simulator runtime is iOS 26.4. iOS 17 runtime compatibility remains
  unverified locally, as recorded in ADR-012.

## Limitations

- The event ID and loopback API address are demo configuration, not user-selectable event
  discovery or production environment configuration.
- A broad retry/cancellation policy, caching, hold creation, and confirmation remain
  future vertical slices; this screen only loads a read snapshot.
