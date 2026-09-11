from dataclasses import dataclass
from typing import Literal
from uuid import UUID

SeatAvailabilityStatus = Literal["available", "held", "reserved"]


@dataclass(frozen=True, slots=True)
class EventSeatAvailability:
    event_seat_id: UUID
    section: str
    row: str
    number: str
    price_cents: int
    status: SeatAvailabilityStatus


class EventNotFound(Exception):
    pass
