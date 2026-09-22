from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from seatsafe.application.holds import HoldService
from seatsafe.domain.holds import (
    EventSeatNotFound,
    IdempotencyKeyReused,
    SeatHold,
    SeatUnavailable,
)

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
OWNER_ID = UUID("00000000-0000-4000-8000-000000000001")
EVENT_SEAT_ID = UUID("00000000-0000-4000-8000-000000000040")
NEW_HOLD_ID = UUID("00000000-0000-4000-8000-000000000050")
OLD_HOLD_ID = UUID("00000000-0000-4000-8000-000000000051")
IDEMPOTENCY_ID = UUID("00000000-0000-4000-8000-000000000061")


@dataclass(frozen=True)
class FakeStoredRecord:
    request_fingerprint: str
    response_status: int
    response_body: str


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

    async def flush(self) -> None:
        return None


class FakeIdempotencyRepository:
    def __init__(self) -> None:
        self.records: dict[tuple[UUID, str, str], tuple[str, int, str]] = {}
        self.locked_keys: list[tuple[UUID, str, str]] = []

    async def lock_key(self, *, owner_id: UUID, operation: str, key: str) -> None:
        self.locked_keys.append((owner_id, operation, key))

    async def get_record(
        self, *, owner_id: UUID, operation: str, key: str
    ) -> FakeStoredRecord | None:
        record = self.records.get((owner_id, operation, key))
        if record is None:
            return None
        return FakeStoredRecord(*record)

    async def add_record(
        self,
        *,
        id: UUID,
        owner_id: UUID,
        operation: str,
        key: str,
        request_fingerprint: str,
        hold_id: UUID | None,
        reservation_id: UUID | None,
        completed_at: datetime,
        response_body: str,
    ) -> None:
        assert hold_id is not None
        assert reservation_id is None
        self.records[(owner_id, operation, key)] = (request_fingerprint, 201, response_body)


class FakeHoldUnitOfWork:
    def __init__(
        self, repository: FakeHoldRepository, idempotency: FakeIdempotencyRepository
    ) -> None:
        self.holds = repository
        self.idempotency = idempotency
        self.committed = False

    async def __aenter__(self) -> "FakeHoldUnitOfWork":
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


def make_service(repository: FakeHoldRepository) -> tuple[HoldService, FakeHoldUnitOfWork]:
    unit_of_work = FakeHoldUnitOfWork(repository, FakeIdempotencyRepository())
    generated_ids = iter((NEW_HOLD_ID, IDEMPOTENCY_ID, OLD_HOLD_ID, IDEMPOTENCY_ID))
    service = HoldService(
        unit_of_work_factory=lambda: unit_of_work,
        clock=FixedClock(),
        id_factory=lambda: next(generated_ids),
        hold_duration=timedelta(minutes=5),
    )
    return service, unit_of_work


@pytest.mark.asyncio
async def test_create_hold_locks_seat_and_commits_active_hold() -> None:
    repository = FakeHoldRepository()
    service, unit_of_work = make_service(repository)

    result = await service.create_hold(
        event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID, idempotency_key="hold-key-1"
    )

    assert repository.locked_event_seat_ids == [EVENT_SEAT_ID]
    assert repository.added_holds == [
        SeatHold(
            id=NEW_HOLD_ID,
            event_seat_id=EVENT_SEAT_ID,
            owner_id=OWNER_ID,
            status="active",
            created_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
        )
    ]
    assert result.status_code == 201
    assert result.replayed is False
    assert '"id":"00000000-0000-4000-8000-000000000050"' in result.response_body
    assert unit_of_work.committed


@pytest.mark.asyncio
async def test_create_hold_rejects_missing_event_seat_without_commit() -> None:
    repository = FakeHoldRepository()
    repository.event_seat_exists = False
    service, unit_of_work = make_service(repository)

    with pytest.raises(EventSeatNotFound):
        await service.create_hold(
            event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID, idempotency_key="hold-key-1"
        )

    assert not unit_of_work.committed
    assert repository.added_holds == []


@pytest.mark.asyncio
async def test_create_hold_rejects_active_reservation() -> None:
    repository = FakeHoldRepository()
    repository.active_reservation_exists = True
    service, unit_of_work = make_service(repository)

    with pytest.raises(SeatUnavailable):
        await service.create_hold(
            event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID, idempotency_key="hold-key-1"
        )

    assert not unit_of_work.committed


@pytest.mark.asyncio
async def test_create_hold_rejects_unexpired_hold() -> None:
    repository = FakeHoldRepository()
    repository.active_hold = _existing_hold(expires_at=NOW + timedelta(seconds=1))
    service, unit_of_work = make_service(repository)

    with pytest.raises(SeatUnavailable):
        await service.create_hold(
            event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID, idempotency_key="hold-key-1"
        )

    assert repository.expired_hold_ids == []
    assert not unit_of_work.committed


@pytest.mark.asyncio
async def test_create_hold_expires_old_hold_at_exact_deadline() -> None:
    repository = FakeHoldRepository()
    repository.active_hold = _existing_hold(expires_at=NOW)
    service, unit_of_work = make_service(repository)

    await service.create_hold(
        event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID, idempotency_key="hold-key-1"
    )

    assert repository.expired_hold_ids == [OLD_HOLD_ID]
    assert len(repository.added_holds) == 1
    assert unit_of_work.committed


@pytest.mark.asyncio
async def test_create_hold_replays_original_response_for_same_key_and_seat() -> None:
    repository = FakeHoldRepository()
    service, _ = make_service(repository)

    first = await service.create_hold(
        event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID, idempotency_key="hold-key-1"
    )
    replay = await service.create_hold(
        event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID, idempotency_key="hold-key-1"
    )

    assert replay.status_code == first.status_code == 201
    assert replay.response_body == first.response_body
    assert first.replayed is False
    assert replay.replayed is True
    assert len(repository.added_holds) == 1


@pytest.mark.asyncio
async def test_create_hold_rejects_same_key_for_different_seat() -> None:
    repository = FakeHoldRepository()
    service, _ = make_service(repository)
    await service.create_hold(
        event_seat_id=EVENT_SEAT_ID, owner_id=OWNER_ID, idempotency_key="hold-key-1"
    )

    with pytest.raises(IdempotencyKeyReused):
        await service.create_hold(
            event_seat_id=UUID("00000000-0000-4000-8000-000000000041"),
            owner_id=OWNER_ID,
            idempotency_key="hold-key-1",
        )

    assert len(repository.added_holds) == 1


def _existing_hold(*, expires_at: datetime) -> SeatHold:
    return SeatHold(
        id=OLD_HOLD_ID,
        event_seat_id=EVENT_SEAT_ID,
        owner_id=OWNER_ID,
        status="active",
        created_at=NOW - timedelta(minutes=5),
        expires_at=expires_at,
    )
