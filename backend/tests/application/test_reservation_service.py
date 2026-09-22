from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from seatsafe.application.reservations import ReservationService
from seatsafe.domain.holds import (
    HoldExpired,
    HoldNotActive,
    HoldOwnerMismatch,
    IdempotencyKeyReused,
    SeatUnavailable,
)
from seatsafe.domain.reservations import Reservation

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
OWNER_ID = UUID("00000000-0000-4000-8000-000000000001")
OTHER_OWNER_ID = UUID("00000000-0000-4000-8000-000000000002")
EVENT_SEAT_ID = UUID("00000000-0000-4000-8000-000000000040")
HOLD_ID = UUID("00000000-0000-4000-8000-000000000050")
OTHER_HOLD_ID = UUID("00000000-0000-4000-8000-000000000051")
RESERVATION_ID = UUID("00000000-0000-4000-8000-000000000060")
IDEMPOTENCY_ID = UUID("00000000-0000-4000-8000-000000000061")


@dataclass
class FakeHold:
    id: UUID
    event_seat_id: UUID
    owner_id: UUID
    status: str
    expires_at: datetime


@dataclass(frozen=True)
class FakeIdempotencyRecord:
    request_fingerprint: str
    response_status: int
    response_body: str


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeReservationRepository:
    def __init__(self) -> None:
        self.holds = {
            HOLD_ID: FakeHold(
                HOLD_ID, EVENT_SEAT_ID, OWNER_ID, "active", NOW + timedelta(minutes=5)
            ),
            OTHER_HOLD_ID: FakeHold(
                OTHER_HOLD_ID,
                UUID("00000000-0000-4000-8000-000000000041"),
                OWNER_ID,
                "active",
                NOW + timedelta(minutes=5),
            ),
        }
        self.records: dict[tuple[UUID, str], FakeIdempotencyRecord] = {}
        self.locked_keys: list[tuple[UUID, str]] = []
        self.locked_seats: list[UUID] = []
        self.active_reservation = False
        self.reservations: list[Reservation] = []

    async def lock_idempotency_key(self, *, owner_id: UUID, key: str) -> None:
        self.locked_keys.append((owner_id, key))

    async def get_idempotency_record(
        self,
        *,
        owner_id: UUID,
        key: str,
    ) -> FakeIdempotencyRecord | None:
        return self.records.get((owner_id, key))

    async def get_hold(self, hold_id: UUID) -> FakeHold | None:
        return self.holds.get(hold_id)

    async def lock_event_seat(self, event_seat_id: UUID) -> bool:
        self.locked_seats.append(event_seat_id)
        return True

    async def has_active_reservation(self, event_seat_id: UUID) -> bool:
        return self.active_reservation

    async def set_hold_status(self, hold_id: UUID, status: str) -> None:
        self.holds[hold_id].status = status

    async def add_reservation(self, reservation: Reservation) -> None:
        self.reservations.append(reservation)

    async def flush(self) -> None:
        return None

    async def add_idempotency_record(
        self,
        *,
        id: UUID,
        owner_id: UUID,
        key: str,
        request_fingerprint: str,
        reservation_id: UUID,
        completed_at: datetime,
        response_body: str,
    ) -> None:
        self.records[(owner_id, key)] = FakeIdempotencyRecord(
            request_fingerprint=request_fingerprint,
            response_status=201,
            response_body=response_body,
        )


class FakeReservationUnitOfWork:
    def __init__(self, repository: FakeReservationRepository) -> None:
        self.reservations = repository
        self.commits = 0

    async def __aenter__(self) -> "FakeReservationUnitOfWork":
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1


def make_service(
    repository: FakeReservationRepository,
) -> tuple[ReservationService, FakeReservationUnitOfWork]:
    unit_of_work = FakeReservationUnitOfWork(repository)
    ids = iter((RESERVATION_ID, IDEMPOTENCY_ID, UUID("00000000-0000-4000-8000-000000000062")))
    service = ReservationService(
        unit_of_work_factory=lambda: unit_of_work,
        clock=FixedClock(),
        id_factory=lambda: next(ids),
    )
    return service, unit_of_work


@pytest.mark.asyncio
async def test_confirm_creates_reservation_and_same_key_replays_original_response() -> None:
    repository = FakeReservationRepository()
    service, unit_of_work = make_service(repository)

    first = await service.confirm(hold_id=HOLD_ID, owner_id=OWNER_ID, idempotency_key="key-1")
    replay = await service.confirm(hold_id=HOLD_ID, owner_id=OWNER_ID, idempotency_key="key-1")

    assert first.status_code == replay.status_code == 201
    assert first.response_body == replay.response_body
    assert first.replayed is False
    assert replay.replayed is True
    assert len(repository.reservations) == 1
    assert repository.holds[HOLD_ID].status == "confirmed"
    assert unit_of_work.commits == 1
    assert repository.locked_keys == [(OWNER_ID, "key-1"), (OWNER_ID, "key-1")]


@pytest.mark.asyncio
async def test_confirm_rejects_same_key_with_different_hold() -> None:
    repository = FakeReservationRepository()
    service, _ = make_service(repository)
    await service.confirm(hold_id=HOLD_ID, owner_id=OWNER_ID, idempotency_key="key-1")

    with pytest.raises(IdempotencyKeyReused):
        await service.confirm(
            hold_id=OTHER_HOLD_ID,
            owner_id=OWNER_ID,
            idempotency_key="key-1",
        )

    assert len(repository.reservations) == 1
    assert repository.holds[OTHER_HOLD_ID].status == "active"


@pytest.mark.asyncio
async def test_confirm_rejects_hold_owned_by_another_user() -> None:
    repository = FakeReservationRepository()
    service, unit_of_work = make_service(repository)

    with pytest.raises(HoldOwnerMismatch):
        await service.confirm(
            hold_id=HOLD_ID,
            owner_id=OTHER_OWNER_ID,
            idempotency_key="other-user-key",
        )

    assert repository.reservations == []
    assert unit_of_work.commits == 0


@pytest.mark.asyncio
async def test_confirm_expires_hold_and_rejects_confirmation_at_deadline() -> None:
    repository = FakeReservationRepository()
    repository.holds[HOLD_ID].expires_at = NOW
    service, unit_of_work = make_service(repository)

    with pytest.raises(HoldExpired):
        await service.confirm(hold_id=HOLD_ID, owner_id=OWNER_ID, idempotency_key="key-1")

    assert repository.holds[HOLD_ID].status == "expired"
    assert repository.reservations == []
    assert unit_of_work.commits == 1


@pytest.mark.asyncio
async def test_confirm_rejects_inactive_hold() -> None:
    repository = FakeReservationRepository()
    repository.holds[HOLD_ID].status = "released"
    service, unit_of_work = make_service(repository)

    with pytest.raises(HoldNotActive):
        await service.confirm(hold_id=HOLD_ID, owner_id=OWNER_ID, idempotency_key="key-1")

    assert repository.reservations == []
    assert unit_of_work.commits == 0


@pytest.mark.asyncio
async def test_confirm_rejects_when_active_reservation_exists() -> None:
    repository = FakeReservationRepository()
    repository.active_reservation = True
    service, unit_of_work = make_service(repository)

    with pytest.raises(SeatUnavailable):
        await service.confirm(hold_id=HOLD_ID, owner_id=OWNER_ID, idempotency_key="key-1")

    assert repository.reservations == []
    assert unit_of_work.commits == 0
