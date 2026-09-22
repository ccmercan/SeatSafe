from uuid import UUID

from fastapi.testclient import TestClient

from seatsafe.api.dependencies import get_reservation_service
from seatsafe.config import Settings
from seatsafe.domain.holds import IdempotencyKeyReused
from seatsafe.domain.reservations import ConfirmationResult
from seatsafe.main import create_app

HOLD_ID = UUID("00000000-0000-4000-8000-000000000050")
EVENT_SEAT_ID = UUID("00000000-0000-4000-8000-000000000040")
RESERVATION_ID = UUID("00000000-0000-4000-8000-000000000060")
RESPONSE_BODY = (
    '{"id":"00000000-0000-4000-8000-000000000060",'
    '"hold_id":"00000000-0000-4000-8000-000000000050",'
    '"event_seat_id":"00000000-0000-4000-8000-000000000040",'
    '"status":"active","confirmed_at":"2026-09-11T12:00:00Z"}'
)


class SuccessfulReservationService:
    async def confirm(
        self,
        *,
        hold_id: UUID,
        owner_id: UUID,
        idempotency_key: str,
    ) -> ConfirmationResult:
        assert hold_id == HOLD_ID
        assert idempotency_key == "confirmation-1"
        return ConfirmationResult(201, RESPONSE_BODY, replayed=False)


class ReusedKeyReservationService:
    async def confirm(
        self,
        *,
        hold_id: UUID,
        owner_id: UUID,
        idempotency_key: str,
    ) -> ConfirmationResult:
        raise IdempotencyKeyReused


def test_confirm_reservation_uses_header_and_returns_created_contract() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_reservation_service] = SuccessfulReservationService

    with TestClient(app) as client:
        response = client.post(
            "/v1/reservations",
            json={"hold_id": str(HOLD_ID)},
            headers={"Idempotency-Key": "confirmation-1"},
        )

    assert response.status_code == 201
    assert response.text == RESPONSE_BODY
    assert response.json() == {
        "id": str(RESERVATION_ID),
        "hold_id": str(HOLD_ID),
        "event_seat_id": str(EVENT_SEAT_ID),
        "status": "active",
        "confirmed_at": "2026-09-11T12:00:00Z",
    }


def test_confirm_reservation_requires_idempotency_key() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_reservation_service] = SuccessfulReservationService

    with TestClient(app) as client:
        response = client.post("/v1/reservations", json={"hold_id": str(HOLD_ID)})

    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"


def test_confirm_reservation_maps_reused_key_to_problem_details() -> None:
    app = create_app(Settings(environment="test"))
    app.dependency_overrides[get_reservation_service] = ReusedKeyReservationService

    with TestClient(app) as client:
        response = client.post(
            "/v1/reservations",
            json={"hold_id": str(HOLD_ID)},
            headers={"Idempotency-Key": "confirmation-1"},
        )

    assert response.status_code == 409
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "idempotency_key_reused"
