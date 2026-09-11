from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SeatHold:
    id: UUID
    event_seat_id: UUID
    owner_id: UUID
    status: str
    created_at: datetime
    expires_at: datetime


class EventSeatNotFound(Exception):
    pass


class SeatUnavailable(Exception):
    pass
