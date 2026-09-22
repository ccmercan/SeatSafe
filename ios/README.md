# iOS client

## What exists now

The first vertical slice loads the deterministic demo event's seat-availability snapshot
from the backend. The view renders loading, empty, error, and result states. Its
`SeatListModel` owns UI state; the injected `SeatService` protocol separates feature
behavior from HTTP and makes unit tests deterministic. See [ADR-013](../docs/decisions/013-use-lightweight-swiftui-feature-models.md).

The configured API address is `http://127.0.0.1:8000`, using the existing endpoint
`GET /v1/events/00000000-0000-4000-8000-000000000020/seats`. `Info.plist` allows
App Transport Security local networking only; it does not turn off ATS for remote hosts.

## Open and run

1. Start the backend by following [backend/README.md](../backend/README.md).
2. Open `SeatSafe.xcodeproj` in Xcode.
3. Select the `SeatSafe` scheme and an iOS simulator, then Run.
4. Run tests with `DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild -project ios/SeatSafe.xcodeproj -scheme SeatSafe -destination 'platform=iOS Simulator,name=iPhone 17 Pro' test`.

The project targets iOS 17. The available development simulator is iOS 26.4, so local
execution does not yet prove runtime behavior on the minimum iOS version.
