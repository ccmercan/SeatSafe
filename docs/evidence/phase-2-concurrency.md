# Phase 2 evidence: client concurrency and cancellation

- **Date:** 2026-09-22
- **Scope:** prevent stale seat data from replacing newer state; define local task-cancellation
  behavior; protect in-flight hold and confirmation operations against duplicate actions.

## Plain-language explanation

Network requests can finish in a different order than they started. For example, the user
can open Event A, then Event B, but Event A's slower response might arrive last. The app
must not show Event A's old seats on Event B's screen. Similarly, cancelling the app's wait
for a reservation does not prove the server stopped working, so the app keeps the same
request IDs and keys until it can safely recover the result.

Here “cancellation” means cancelling local asynchronous work. It does not mean the user
cancels a confirmed reservation; that separate product capability has not been implemented.

## Implemented

- Each seat-list load receives a request ID. Only the latest request may publish seats or
  an error. A late response from an older event request is ignored.
- If the current seat-load task is cancelled, the model returns to its neutral `idle`
  state rather than presenting cancellation as a network failure. Even if an injected
  service returns after cancellation, its result is not published.
- Cancelling an in-flight hold or confirmation leaves the outcome `uncertain` and retains
  the exact seat/hold ID and idempotency key. A retry sends the same logical request.
- While a hold or confirmation call is awaiting its service, a repeated call is rejected
  by the model's in-flight state guard. This is client-side duplicate suppression; the
  server's idempotency and database constraints remain the correctness boundary.
- Controlled actor-based test services suspend requests on continuations. Tests choose
  when a request is cancelled or completed, so their ordering is deterministic and does
  not depend on arbitrary sleeps.

## Validation

Command:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  xcodebuild -project ios/SeatSafe.xcodeproj -scheme SeatSafe \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  -derivedDataPath /private/tmp/seatsafe-phase2-derived \
  -only-testing:SeatSafeTests test
```

Result: **21 iOS unit tests passed, 0 failures** on the available iOS 26.4 simulator. The
new cases specifically cover late event responses, cancelled seat loads, cancelled hold
and confirmation writes followed by same-key retries, and repeated in-flight hold and
confirmation actions producing only one request each. `swift-format lint --strict` also
passed for the changed Swift sources.

The real-backend visible confirmation journey is separately recorded in
[Phase 3 UI smoke evidence](phase-3-ui-smoke.md). That check does not replace these faster,
controlled model tests.

## Limitation

Replacing an event load protects UI state by ignoring an obsolete response; the model does
not yet retain a separate task handle to forcibly stop every replaced network request.
Cancellation of the screen-owned SwiftUI task is handled. The current app uses one seeded
event, so searchable multi-event navigation remains future product work.
