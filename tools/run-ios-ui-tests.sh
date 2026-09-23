#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$REPO_ROOT/infrastructure/compose.test.yaml"
BACKEND_DIR="$REPO_ROOT/backend"
DERIVED_DATA_PATH="${SEATSAFE_UI_DERIVED_DATA_PATH:-${TMPDIR:-/tmp}/seatsafe-ui-derived}"
RESULT_BUNDLE_PATH="${TMPDIR:-/tmp}/SeatSafe-UI-$(date +%Y%m%d-%H%M%S).xcresult"
API_LOG_PATH="$(mktemp -t seatsafe-ui-api)"
API_PID=""
COMPOSE_STARTED="false"

cleanup() {
    local result=$?

    trap - EXIT INT TERM
    if [[ -n "$API_PID" ]]; then
        kill "$API_PID" 2>/dev/null || true
        wait "$API_PID" 2>/dev/null || true
    fi
    if [[ "$COMPOSE_STARTED" == "true" ]]; then
        docker compose -f "$COMPOSE_FILE" down --remove-orphans || true
    fi
    if [[ $result -ne 0 ]]; then
        echo "UI tests failed. Xcode result bundle: $RESULT_BUNDLE_PATH" >&2
        echo "API log: $API_LOG_PATH" >&2
        tail -n 80 "$API_LOG_PATH" >&2 || true
    else
        echo "Xcode result bundle: $RESULT_BUNDLE_PATH"
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

echo "Starting the local API..."
(
    cd "$BACKEND_DIR"
    exec env SEATSAFE_ENVIRONMENT=test .venv/bin/python -m uvicorn \
        seatsafe.main:app --app-dir src --host 127.0.0.1 --port 8000
) >"$API_LOG_PATH" 2>&1 &
API_PID=$!

api_ready="false"
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

echo "Running the SeatSafe Xcode unit and UI test targets..."
"$DEVELOPER_DIR/usr/bin/xcodebuild" \
    -project "$REPO_ROOT/ios/SeatSafe.xcodeproj" \
    -scheme SeatSafe \
    -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
    -derivedDataPath "$DERIVED_DATA_PATH" \
    -resultBundlePath "$RESULT_BUNDLE_PATH" \
    test
