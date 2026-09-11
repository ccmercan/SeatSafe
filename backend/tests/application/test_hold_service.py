from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from seatsafe.application.holds import HoldService
from seatsafe.domain.holds import EventSeatNotFound, SeatHold, SeatUnavailable

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
OWNER_ID = UUID("00000000-0000-4000-8000-000000000001")
EVENT_SEAT_ID = UUID("00000000-0000-4000-8000-000000000040")
NEW_HOLD_ID = UUID("00000000-0000-4000-8000-000000000050")
OLD_HOLD_ID = UUID("00000000-0000-4000-8000-000000000051")


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeHoldRepository:
    def __init__(self) -> None:
        self.event_seat_exists = True
        self.active_reservation_exists = False
        self.active_hold: SeatHold | None = None
        self.expired_hold_ids: list[UUID] = []
        self.added_holds: list[SeatHold] = []
        self.locked_event_seat_ids: list[UUID] = []

    async def lock_event_seat(self, event_seat_id: UUID) -> bool:
        self.locked_event_seat_ids.append(event_seat_id)
        return self.event_seat_exists

    async def has_active_reservation(self, event_seat_id: UUID) -> bool:
        return self.active_reservation_exists

    async def get_active_hold(self, event_seat_id: UUID) -> SeatHold | None:
        return self.active_hold

    async def expire_hold(self, hold_id: UUID) -> None:
        self.expired_hold_ids.append(hold_id)

    async def add_hold(self, hold: SeatHold) -> None:
        self.added_holds.append(hold)


class FakeHoldUnitOfWork:
    def __init__(self, repository: FakeHoldRepository) -> None:
        self.holds = repository
        self.committed = False

    async def __aenter__(self) -> "FakeHoldUnitOfWork":
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def make_service(repository: FakeHoldRepository) -> tuple[HoldService, FakeHoldUnitOfWork]:
    unit_of_work = FakeHoldUnitOfWork(repository)
    service = HoldService(
        unit_of_work_factory=lambda: unit_of_work,
        clock=FixedClock(),
        id_factory=lambda: NEW_HOLD_ID,
        hold_duration=timedelta(minutes=5),
    )
    return service, unit_of_work


@pytest.mark.asyncio
async def test_create_hold_locks_seat_and_commits_active_hold() -> None:
    repository = FakeHoldRepository()
    service, unit_of_work = make_service(repository)

    result = await service.create_hold(event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID)

    assert repository.locked_event_seat_ids == [EVENT_SEAT_ID]
    assert repository.added_holds == [result]
    assert result == SeatHold(
        id=NEW_HOLD_ID,
        event_seat_id=EVENT_SEAT_ID,
        owner_id=OWNER_ID,
        status="active",
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=5),
    )
    assert unit_of_work.committed


@pytest.mark.asyncio
async def test_create_hold_rejects_missing_event_seat_without_commit() -> None:
    repository = FakeHoldRepository()
    repository.event_seat_exists = False
    service, unit_of_work = make_service(repository)

    with pytest.raises(EventSeatNotFound):
        await service.create_hold(event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID)

    assert not unit_of_work.committed
    assert repository.added_holds == []


@pytest.mark.asyncio
async def test_create_hold_rejects_active_reservation() -> None:
    repository = FakeHoldRepository()
    repository.active_reservation_exists = True
    service, unit_of_work = make_service(repository)

    with pytest.raises(SeatUnavailable):
        await service.create_hold(event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID)

    assert not unit_of_work.committed


@pytest.mark.asyncio
async def test_create_hold_rejects_unexpired_hold() -> None:
    repository = FakeHoldRepository()
    repository.active_hold = _existing_hold(expires_at=NOW + timedelta(seconds=1))
    service, unit_of_work = make_service(repository)

    with pytest.raises(SeatUnavailable):
        await service.create_hold(event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID)

    assert repository.expired_hold_ids == []
    assert not unit_of_work.committed


@pytest.mark.asyncio
async def test_create_hold_expires_old_hold_at_exact_deadline() -> None:
    repository = FakeHoldRepository()
    repository.active_hold = _existing_hold(expires_at=NOW)
    service, unit_of_work = make_service(repository)

    result = await service.create_hold(event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID)

    assert repository.expired_hold_ids == [OLD_HOLD_ID]
    assert repository.added_holds == [result]
    assert unit_of_work.committed


def _existing_hold(*, expires_at: datetime) -> SeatHold:
    return SeatHold(
        id=OLD_HOLD_ID,
        event_seat_id=EVENT_SEAT_ID,
        owner_id=OWNER_ID,
        status="active",
        created_at=NOW - timedelta(minutes=5),
        expires_at=expires_at,
    )
