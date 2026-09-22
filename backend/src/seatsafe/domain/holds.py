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


@dataclass(frozen=True, slots=True)
class HoldCreationResult:
    status_code: int
    response_body: str
    replayed: bool


class EventSeatNotFound(Exception):
    pass


class SeatUnavailable(Exception):
    pass


class HoldNotFound(Exception):
    pass


class HoldOwnerMismatch(Exception):
    pass


class HoldExpired(Exception):
    pass


class HoldNotActive(Exception):
    pass


class IdempotencyKeyReused(Exception):
    pass
