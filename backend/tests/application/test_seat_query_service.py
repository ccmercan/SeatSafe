from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from seatsafe.application.seats import SeatQueryService
from seatsafe.domain.seats import EventNotFound, EventSeatAvailability

NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
EVENT_ID = UUID("00000000-0000-4000-8000-000000000020")
EVENT_SEAT_ID = UUID("00000000-0000-4000-8000-000000000040")


class FixedClock:
    def now(self) -> datetime:
        return NOW


@dataclass(frozen=True)
class FakeEventSeatFact:
    event_seat_id: UUID = EVENT_SEAT_ID
    section: str = "Main"
    row: str = "A"
    number: str = "1"
    price_cents: int = 2500
    active_hold_expires_at: datetime | None = None
    has_active_reservation: bool = False


class FakeSeatRepository:
    def __init__(self, result: list[FakeEventSeatFact] | None) -> None:
        self.result = result

    async def list_for_event(self, event_id: UUID) -> list[FakeEventSeatFact] | None:
        assert event_id == EVENT_ID
        return self.result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fact", "expected_status"),
    [
        (FakeEventSeatFact(), "available"),
        (FakeEventSeatFact(active_hold_expires_at=NOW + timedelta(seconds=1)), "held"),
        (FakeEventSeatFact(active_hold_expires_at=NOW), "available"),
        (
            FakeEventSeatFact(
                active_hold_expires_at=NOW + timedelta(seconds=1),
                has_active_reservation=True,
            ),
            "reserved",
        ),
    ],
)
async def test_list_event_seats_computes_public_status(
    fact: FakeEventSeatFact,
    expected_status: str,
) -> None:
    service = SeatQueryService(repository=FakeSeatRepository([fact]), clock=FixedClock())

    result = await service.list_event_seats(EVENT_ID)

    assert result == [
        EventSeatAvailability(
            event_seat_id=EVENT_SEAT_ID,
            section="Main",
            row="A",
            number="1",
            price_cents=2500,
            status=expected_status,
        )
    ]


@pytest.mark.asyncio
async def test_list_event_seats_rejects_missing_event() -> None:
    service = SeatQueryService(repository=FakeSeatRepository(None), clock=FixedClock())

    with pytest.raises(EventNotFound):
        await service.list_event_seats(EVENT_ID)


@pytest.mark.asyncio
async def test_list_event_seats_allows_existing_event_with_no_seats() -> None:
    service = SeatQueryService(repository=FakeSeatRepository([]), clock=FixedClock())

    assert await service.list_event_seats(EVENT_ID) == []
