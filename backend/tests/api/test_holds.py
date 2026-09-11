from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient

from seatsafe.api.dependencies import get_hold_service
from seatsafe.config import Settings
from seatsafe.domain.holds import SeatHold, SeatUnavailable
from seatsafe.main import create_app

OWNER_ID = UUID("00000000-0000-4000-8000-000000000001")
EVENT_SEAT_ID = UUID("00000000-0000-4000-8000-000000000040")
HOLD_ID = UUID("00000000-0000-4000-8000-000000000050")
NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)


class SuccessfulHoldService:
    async def create_hold(self, *, event_seat_id: UUID, owner_id: UUID) -> SeatHold:
        return SeatHold(
            id=HOLD_ID,
            event_seat_id=event_seat_id,
            owner_id=owner_id,
            status="active",
            created_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
        )


class UnavailableHoldService:
    async def create_hold(self, *, event_seat_id: UUID, owner_id: UUID) -> SeatHold:
        raise SeatUnavailable


def test_create_hold_returns_created_contract() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_hold_service] = SuccessfulHoldService

    with TestClient(app) as client:
        response = client.post("/v1/holds", json={"event_seat_id": str(EVENT_SEAT_ID)})

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
        response = client.post("/v1/holds", json={"event_seat_id": str(EVENT_SEAT_ID)})

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "seat_unavailable"
