import hashlib
import json
from collections.abc import Callable
from datetime import datetime
from typing import Protocol, Self
from uuid import UUID

from seatsafe.application.holds import Clock
from seatsafe.domain.holds import (
    HoldExpired,
    HoldNotActive,
    HoldNotFound,
    HoldOwnerMismatch,
    IdempotencyKeyReused,
    SeatUnavailable,
)
from seatsafe.domain.reservations import ConfirmationResult, Reservation

OPERATION = "confirm_reservation"


class ConfirmableHold(Protocol):
    id: UUID
    event_seat_id: UUID
    owner_id: UUID
    status: str
    expires_at: datetime


class StoredConfirmation(Protocol):
    request_fingerprint: str
    response_status: int
    response_body: str


class ReservationRepository(Protocol):
    async def lock_idempotency_key(self, *, owner_id: UUID, key: str) -> None: ...

    async def get_idempotency_record(
        self, *, owner_id: UUID, key: str
    ) -> StoredConfirmation | None: ...

    async def get_hold(self, hold_id: UUID) -> ConfirmableHold | None: ...

    async def lock_event_seat(self, event_seat_id: UUID) -> bool: ...

    async def has_active_reservation(self, event_seat_id: UUID) -> bool: ...

    async def set_hold_status(self, hold_id: UUID, status: str) -> None: ...

    async def add_reservation(self, reservation: Reservation) -> None: ...

    async def flush(self) -> None: ...

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
    ) -> None: ...


class ReservationUnitOfWork(Protocol):
    reservations: ReservationRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class ReservationService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], ReservationUnitOfWork],
        clock: Clock,
        id_factory: Callable[[], UUID],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._id_factory = id_factory

    async def confirm(
        self,
        *,
        hold_id: UUID,
        owner_id: UUID,
        idempotency_key: str,
    ) -> ConfirmationResult:
        fingerprint = _fingerprint(hold_id)
        expired = False

        async with self._unit_of_work_factory() as unit_of_work:
            repository = unit_of_work.reservations
            await repository.lock_idempotency_key(owner_id=owner_id, key=idempotency_key)
            previous = await repository.get_idempotency_record(
                owner_id=owner_id,
                key=idempotency_key,
            )
            if previous is not None:
                if previous.request_fingerprint != fingerprint:
                    raise IdempotencyKeyReused
                return ConfirmationResult(
                    status_code=previous.response_status,
                    response_body=previous.response_body,
                    replayed=True,
                )

            hold = await repository.get_hold(hold_id)
            if hold is None:
                raise HoldNotFound
            if not await repository.lock_event_seat(hold.event_seat_id):
                raise HoldNotFound

            # Re-read after obtaining the seat lock so state reflects any earlier transition.
            hold = await repository.get_hold(hold_id)
            if hold is None:
                raise HoldNotFound
            if hold.owner_id != owner_id:
                raise HoldOwnerMismatch
            if hold.status != "active":
                raise HoldNotActive

            now = self._clock.now()
            if hold.expires_at <= now:
                await repository.set_hold_status(hold.id, "expired")
                await unit_of_work.commit()
                expired = True
            else:
                if await repository.has_active_reservation(hold.event_seat_id):
                    raise SeatUnavailable

                reservation = Reservation(
                    id=self._id_factory(),
                    hold_id=hold.id,
                    event_seat_id=hold.event_seat_id,
                    owner_id=owner_id,
                    status="active",
                    confirmed_at=now,
                )
                response_body = _response_body(reservation)
                await repository.set_hold_status(hold.id, "confirmed")
                await repository.add_reservation(reservation)
                # The idempotency row has a foreign key to this reservation.
                # Flush sends the reservation INSERT first but does not commit;
                # both rows still succeed or roll back together.
                await repository.flush()
                await repository.add_idempotency_record(
                    id=self._id_factory(),
                    owner_id=owner_id,
                    key=idempotency_key,
                    request_fingerprint=fingerprint,
                    reservation_id=reservation.id,
                    completed_at=now,
                    response_body=response_body,
                )
                await unit_of_work.commit()
                return ConfirmationResult(
                    status_code=201,
                    response_body=response_body,
                    replayed=False,
                )

        if expired:
            raise HoldExpired
        raise RuntimeError("Confirmation ended without a result.")


def _fingerprint(hold_id: UUID) -> str:
    canonical_request = json.dumps({"hold_id": str(hold_id)}, separators=(",", ":"))
    return hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()


def _response_body(reservation: Reservation) -> str:
    confirmed_at = reservation.confirmed_at.isoformat().replace("+00:00", "Z")
    response = {
        "id": str(reservation.id),
        "hold_id": str(reservation.hold_id),
        "event_seat_id": str(reservation.event_seat_id),
        "status": "active",
        "confirmed_at": confirmed_at,
    }
    return json.dumps(response, separators=(",", ":"))
