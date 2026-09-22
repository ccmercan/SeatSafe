from datetime import UTC, datetime
from uuid import UUID

from fastapi.testclient import TestClient

from seatsafe.api.dependencies import get_hold_service
from seatsafe.config import Settings
from seatsafe.domain.holds import HoldCreationResult, IdempotencyKeyReused, SeatUnavailable
from seatsafe.main import create_app

OWNER_ID = UUID("00000000-0000-4000-8000-000000000001")
EVENT_SEAT_ID = UUID("00000000-0000-4000-8000-000000000040")
HOLD_ID = UUID("00000000-0000-4000-8000-000000000050")
NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


class SuccessfulHoldService:
    async def create_hold(
        self, *, event_seat_id: UUID, owner_id: UUID, idempotency_key: str
    ) -> HoldCreationResult:
        assert idempotency_key == "hold-attempt-1"
        return HoldCreationResult(
            201,
            '{"id":"00000000-0000-4000-8000-000000000050",'
            '"event_seat_id":"00000000-0000-4000-8000-000000000040",'
            '"status":"active","expires_at":"2026-09-11T12:05:00Z"}',
            False,
        )


class UnavailableHoldService:
    async def create_hold(
        self, *, event_seat_id: UUID, owner_id: UUID, idempotency_key: str
    ) -> HoldCreationResult:
        raise SeatUnavailable


class ReusedKeyHoldService:
    async def create_hold(
        self, *, event_seat_id: UUID, owner_id: UUID, idempotency_key: str
    ) -> HoldCreationResult:
        raise IdempotencyKeyReused


def test_create_hold_returns_created_contract() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_hold_service] = SuccessfulHoldService

    with TestClient(app) as client:
        response = client.post(
            "/v1/holds",
            json={"event_seat_id": str(EVENT_SEAT_ID)},
            headers={"Idempotency-Key": "hold-attempt-1"},
        )

    assert response.status_code == 201
    assert response.json() == {
        "id": str(HOLD_ID),
        "event_seat_id": str(EVENT_SEAT_ID),
        "status": "active",
        "expires_at": "2026-09-11T12:05:00Z",
    }


def test_create_hold_maps_unavailable_seat_to_problem_details() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_hold_service] = UnavailableHoldService

    with TestClient(app) as client:
        response = client.post(
            "/v1/holds",
            json={"event_seat_id": str(EVENT_SEAT_ID)},
            headers={"Idempotency-Key": "hold-attempt-1"},
        )

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "seat_unavailable"


def test_create_hold_requires_an_idempotency_key() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_hold_service] = SuccessfulHoldService

    with TestClient(app) as client:
        response = client.post("/v1/holds", json={"event_seat_id": str(EVENT_SEAT_ID)})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"


def test_create_hold_maps_reused_key_to_problem_details() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_hold_service] = ReusedKeyHoldService

    with TestClient(app) as client:
        response = client.post(
            "/v1/holds",
            json={"event_seat_id": str(EVENT_SEAT_ID)},
            headers={"Idempotency-Key": "hold-attempt-1"},
        )

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "idempotency_key_reused"
