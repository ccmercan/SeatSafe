from uuid import UUID

from fastapi.testclient import TestClient

from seatsafe.api.dependencies import get_seat_query_service
from seatsafe.config import Settings
from seatsafe.domain.seats import EventNotFound, EventSeatAvailability
from seatsafe.main import create_app

EVENT_ID = UUID("00000000-0000-4000-8000-000000000020")
EVENT_SEAT_ID = UUID("00000000-0000-4000-8000-000000000040")


class SuccessfulSeatQueryService:
    async def list_event_seats(self, event_id: UUID) -> list[EventSeatAvailability]:
        assert event_id == EVENT_ID
        return [
            EventSeatAvailability(
                event_seat_id=EVENT_SEAT_ID,
                section="Main",
                row="A",
                number="1",
                price_cents=2500,
                status="available",
            )
        ]


class MissingEventSeatQueryService:
    async def list_event_seats(self, event_id: UUID) -> list[EventSeatAvailability]:
        raise EventNotFound


def test_list_event_seats_returns_snapshot_contract() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_seat_query_service] = SuccessfulSeatQueryService

    with TestClient(app) as client:
        response = client.get(f"/v1/events/{EVENT_ID}/seats")

    assert response.status_code == 200
    assert response.json() == {
        "event_id": str(EVENT_ID),
        "seats": [
            {
                "event_seat_id": str(EVENT_SEAT_ID),
                "section": "Main",
                "row": "A",
                "number": "1",
                "price_cents": 2500,
                "status": "available",
            }
        ],
    }


def test_list_event_seats_maps_missing_event_to_problem_details() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_seat_query_service] = MissingEventSeatQueryService

    with TestClient(app) as client:
        response = client.get(f"/v1/events/{EVENT_ID}/seats")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "resource_not_found"
