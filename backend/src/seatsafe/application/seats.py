from datetime import datetime
from typing import Protocol
from uuid import UUID

from seatsafe.application.holds import Clock
from seatsafe.domain.seats import EventNotFound, EventSeatAvailability, SeatAvailabilityStatus


class EventSeatFact(Protocol):
    event_seat_id: UUID
    section: str
    row: str
    number: str
    price_cents: int
    active_hold_expires_at: datetime | None
    has_active_reservation: bool


class SeatQueryRepository(Protocol):
    async def list_for_event(self, event_id: UUID) -> list[EventSeatFact] | None: ...


class SeatQueryService:
    def __init__(self, *, repository: SeatQueryRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    async def list_event_seats(self, event_id: UUID) -> list[EventSeatAvailability]:
        facts = await self._repository.list_for_event(event_id)
        if facts is None:
            raise EventNotFound

        now = self._clock.now()
        return [
            EventSeatAvailability(
                event_seat_id=fact.event_seat_id,
                section=fact.section,
                row=fact.row,
                number=fact.number,
                price_cents=fact.price_cents,
                status=self._status(fact, now),
            )
            for fact in facts
        ]

    @staticmethod
    def _status(fact: EventSeatFact, now: datetime) -> SeatAvailabilityStatus:
        if fact.has_active_reservation:
            return "reserved"
        if fact.active_hold_expires_at is not None and fact.active_hold_expires_at > now:
            return "held"
        return "available"
