from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Reservation:
    id: UUID
    hold_id: UUID
    event_seat_id: UUID
    owner_id: UUID
    status: str
    confirmed_at: datetime


@dataclass(frozen=True, slots=True)
class ConfirmationResult:
    status_code: int
    response_body: str
    replayed: bool
