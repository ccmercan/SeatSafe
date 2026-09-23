#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infrastructure/compose.test.yaml"
BACKEND_DIR="$REPO_ROOT/backend"
DERIVED_DATA_PATH="${SEATSAFE_UI_DERIVED_DATA_PATH:-${TMPDIR:-/tmp}/seatsafe-ui-derived}"
RESULT_BUNDLE_PATH="${TMPDIR:-/tmp}/SeatSafe-UI-$(date +%Y%m%d-%H%M%S).xcresult"
EXPIRATION_RESULT_BUNDLE_PATH="${TMPDIR:-/tmp}/SeatSafe-UI-expiration-$(date +%Y%m%d-%H%M%S).xcresult"
ERROR_RESULT_BUNDLE_PATH="${TMPDIR:-/tmp}/SeatSafe-UI-api-unavailable-$(date +%Y%m%d-%H%M%S).xcresult"
EXPIRATION_HOLD_DURATION_SECONDS="8"
API_LOG_PATH="$(mktemp -t seatsafe-ui-api)"
API_PID=""
COMPOSE_STARTED="false"
EXPIRATION_TEST_STARTED="false"
ERROR_TEST_STARTED="false"

stop_api() {
    if [[ -n "$API_PID" ]]; then
        kill "$API_PID" 2>/dev/null || true
        wait "$API_PID" 2>/dev/null || true
        API_PID=""
    fi
}

wait_for_api() {
    local api_ready="false"
    for _ in {1..30}; do
        if curl --fail --silent http://127.0.0.1:8000/health >/dev/null; then
            api_ready="true"
            break
        fi
        if ! kill -0 "$API_PID" 2>/dev/null; then
            break
        fi
        sleep 1
    done

    if [[ "$api_ready" != "true" ]]; then
        echo "The local API did not become healthy. See $API_LOG_PATH" >&2
        exit 1
    fi
}

start_api() {
    local hold_duration_seconds="${1:-}"
    echo "Starting the local API..."
    if [[ -n "$hold_duration_seconds" ]]; then
        echo "Using isolated hold duration: ${hold_duration_seconds}s"
        (
            cd "$BACKEND_DIR"
            exec env SEATSAFE_ENVIRONMENT=test \
                SEATSAFE_HOLD_DURATION_SECONDS="$hold_duration_seconds" \
                .venv/bin/python -m uvicorn \
                seatsafe.main:app --app-dir src --host 127.0.0.1 --port 8000
        ) >>"$API_LOG_PATH" 2>&1 &
    else
        (
            cd "$BACKEND_DIR"
            exec env SEATSAFE_ENVIRONMENT=test .venv/bin/python -m uvicorn \
                seatsafe.main:app --app-dir src --host 127.0.0.1 --port 8000
        ) >>"$API_LOG_PATH" 2>&1 &
    fi
    API_PID=$!
    wait_for_api
}

restart_test_simulator() {
    local simulator_id
    simulator_id="$(
        "$DEVELOPER_DIR/usr/bin/simctl" list devices available \
            | sed -nE '/iPhone 17 Pro \(/s/.*\(([A-F0-9-]+)\).*/\1/p'
    )"
    if [[ -z "$simulator_id" ]]; then
        echo "The configured iPhone 17 Pro simulator could not be found." >&2
        exit 1
    fi

    echo "Cold-booting the iPhone 17 Pro simulator for an isolated UI run..."
    "$DEVELOPER_DIR/usr/bin/simctl" shutdown "$simulator_id" >/dev/null 2>&1 || true
    "$DEVELOPER_DIR/usr/bin/simctl" boot "$simulator_id"
    "$DEVELOPER_DIR/usr/bin/simctl" bootstatus "$simulator_id" -b
}

cleanup() {
    local result=$?

    trap - EXIT INT TERM
    stop_api
    if [[ "$COMPOSE_STARTED" == "true" ]]; then
        docker compose -f "$COMPOSE_FILE" down --remove-orphans || true
    fi
    if [[ $result -ne 0 ]]; then
        echo "UI tests failed. Xcode result bundle: $RESULT_BUNDLE_PATH" >&2
        if [[ "$EXPIRATION_TEST_STARTED" == "true" ]]; then
            echo "Expiration Xcode result bundle: $EXPIRATION_RESULT_BUNDLE_PATH" >&2
        fi
        if [[ "$ERROR_TEST_STARTED" == "true" ]]; then
            echo "API-unavailable Xcode result bundle: $ERROR_RESULT_BUNDLE_PATH" >&2
        fi
        echo "API log: $API_LOG_PATH" >&2
        tail -n 80 "$API_LOG_PATH" >&2 || true
    else
        echo "Xcode result bundle: $RESULT_BUNDLE_PATH"
        echo "Expiration Xcode result bundle: $EXPIRATION_RESULT_BUNDLE_PATH"
        echo "API-unavailable Xcode result bundle: $ERROR_RESULT_BUNDLE_PATH"
    fi
    exit "$result"
}

trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ ! -x "$BACKEND_DIR/.venv/bin/alembic" ]]; then
    echo "Backend dependencies are missing. Create backend/.venv and install backend dev dependencies first." >&2
    exit 1
fi

if docker compose -f "$COMPOSE_FILE" ps --status running --services 2>/dev/null | grep -qx postgres; then
    echo "SeatSafe's disposable PostgreSQL service is already running. Stop it first; this runner requires exclusive ownership of its test database." >&2
    exit 1
fi

if lsof -nP -iTCP:8000 -sTCP:LISTEN 2>/dev/null | tail -n +2 | grep -q .; then
    echo "Port 8000 is already in use. Stop the existing API before running this isolated UI test." >&2
    exit 1
fi

export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
if [[ ! -x "$DEVELOPER_DIR/usr/bin/xcodebuild" ]]; then
    echo "Xcode was not found at $DEVELOPER_DIR. Set DEVELOPER_DIR to your Xcode installation." >&2
    exit 1
fi

echo "Starting disposable PostgreSQL..."
COMPOSE_STARTED="true"
docker compose -f "$COMPOSE_FILE" up -d --wait

echo "Applying migrations and loading the deterministic demo seats..."
(
    cd "$BACKEND_DIR"
    SEATSAFE_ENVIRONMENT=test .venv/bin/alembic upgrade head
    SEATSAFE_ENVIRONMENT=test .venv/bin/python -m seatsafe.db.demo_seed
)

start_api

echo "Running the SeatSafe Xcode unit and UI test targets..."
"$DEVELOPER_DIR/usr/bin/xcodebuild" \
    -project "$REPO_ROOT/ios/SeatSafe.xcodeproj" \
    -scheme SeatSafe \
    -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
    -derivedDataPath "$DERIVED_DATA_PATH" \
    -resultBundlePath "$RESULT_BUNDLE_PATH" \
    -skip-testing:SeatSafeUITests/ReservationJourneyUITests/testExpiredHoldCannotBeConfirmed \
    -skip-testing:SeatSafeUITests/ReservationJourneyUITests/testUnavailableAPIShowsRetryableError \
    test

echo "Restarting the API with an accelerated duration for the expiration journey..."
stop_api
(
    cd "$BACKEND_DIR"
    SEATSAFE_ENVIRONMENT=test .venv/bin/python -m seatsafe.db.demo_seed
)
start_api "$EXPIRATION_HOLD_DURATION_SECONDS"
restart_test_simulator

echo "Running the isolated hold-expiration UI test..."
EXPIRATION_TEST_STARTED="true"
"$DEVELOPER_DIR/usr/bin/xcodebuild" \
    -project "$REPO_ROOT/ios/SeatSafe.xcodeproj" \
    -scheme SeatSafe \
    -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
    -derivedDataPath "$DERIVED_DATA_PATH" \
    -resultBundlePath "$EXPIRATION_RESULT_BUNDLE_PATH" \
    -only-testing:SeatSafeUITests/ReservationJourneyUITests/testExpiredHoldCannotBeConfirmed \
    test

echo "Stopping the API to test the app's recoverable connection-error screen..."
stop_api
restart_test_simulator

echo "Running the isolated API-unavailable UI test..."
ERROR_TEST_STARTED="true"
"$DEVELOPER_DIR/usr/bin/xcodebuild" \
    -project "$REPO_ROOT/ios/SeatSafe.xcodeproj" \
    -scheme SeatSafe \
    -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
    -derivedDataPath "$DERIVED_DATA_PATH" \
    -resultBundlePath "$ERROR_RESULT_BUNDLE_PATH" \
    -only-testing:SeatSafeUITests/ReservationJourneyUITests/testUnavailableAPIShowsRetryableError \
    test
