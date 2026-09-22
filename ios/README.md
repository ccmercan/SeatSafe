# iOS client

## What exists now

The first vertical slice loads the deterministic demo event's seat-availability snapshot
from the backend. The view renders loading, empty, error, and result states. Its
`SeatListModel` owns UI state; the injected `SeatService` protocol separates feature
behavior from HTTP and makes unit tests deterministic. See [ADR-013](../docs/decisions/013-use-lightweight-swiftui-feature-models.md).

The selected-seat panel can create a temporary server hold. The separate
`HTTPHoldService` sends the seat ID and `Idempotency-Key` to `POST /v1/holds`. The model
saves one reservation flow through `ReservationFlowStore` before network I/O; production
uses UserDefaults and tests inject an in-memory store. It first stores the seat ID + hold
key, then replaces that record with the successful hold + confirmation key. The Confirm
button calls `POST /v1/reservations`; an uncertain reply retries the exact same hold/key,
including after model recreation. Details are in [ADR-014](../docs/decisions/014-use-idempotency-for-hold-creation.md),
[ADR-015](../docs/decisions/015-persist-pending-hold-attempt-locally.md), and
[ADR-016](../docs/decisions/016-persist-pending-confirmation-locally.md).

The configured API address is `http://127.0.0.1:8000`, using the existing endpoint
`GET /v1/events/00000000-0000-4000-8000-000000000020/seats`. `Info.plist` allows
App Transport Security local networking only; it does not turn off ATS for remote hosts.

## Open and run

1. Start the backend by following [backend/README.md](../backend/README.md).
2. Open `SeatSafe.xcodeproj` in Xcode.
3. Select the `SeatSafe` scheme and an iOS simulator, then Run.
4. Run tests with `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -project ios/SeatSafe.xcodeproj -scheme SeatSafe -destination 'platform=iOS Simulator,name=iPhone 17 Pro' test`.
5. Check Swift formatting with `swift-format lint --strict SeatSafe/SeatSafeApp.swift SeatSafe/HoldCreation.swift SeatSafeTests/SeatListModelTests.swift` from `ios/`.

The project targets iOS 17. The available development simulator is iOS 26.4, so local
execution does not yet prove runtime behavior on the minimum iOS version. The backend must
be running to try the live end-to-end flow; automated client tests use stub services and do
not require the backend.
