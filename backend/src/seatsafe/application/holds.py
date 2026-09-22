import hashlib
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol, Self
from uuid import UUID

from seatsafe.application.idempotency import IdempotencyRepository
from seatsafe.domain.holds import (
    EventSeatNotFound,
    HoldCreationResult,
    IdempotencyKeyReused,
    SeatHold,
    SeatUnavailable,
)

CREATE_HOLD_OPERATION = "create_hold"


class Clock(Protocol):
    def now(self) -> datetime: ...


class HoldRepository(Protocol):
    async def lock_event_seat(self, event_seat_id: UUID) -> bool: ...

    async def has_active_reservation(self, event_seat_id: UUID) -> bool: ...

    async def get_active_hold(self, event_seat_id: UUID) -> SeatHold | None: ...

    async def expire_hold(self, hold_id: UUID) -> None: ...

    async def add_hold(self, hold: SeatHold) -> None: ...

    async def flush(self) -> None: ...


class HoldUnitOfWork(Protocol):
    holds: HoldRepository
    idempotency: IdempotencyRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None: ...

    async def commit(self) -> None: ...


class HoldService:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], HoldUnitOfWork],
        clock: Clock,
        id_factory: Callable[[], UUID],
        hold_duration: timedelta,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock
        self._id_factory = id_factory
        self._hold_duration = hold_duration

    async def create_hold(
        self,
        *,
        event_seat_id: UUID,
        owner_id: UUID,
        idempotency_key: str,
    ) -> HoldCreationResult:
        async with self._unit_of_work_factory() as unit_of_work:
            await unit_of_work.idempotency.lock_key(
                owner_id=owner_id,
                operation=CREATE_HOLD_OPERATION,
                key=idempotency_key,
            )
            previous = await unit_of_work.idempotency.get_record(
                owner_id=owner_id,
                operation=CREATE_HOLD_OPERATION,
                key=idempotency_key,
            )
            fingerprint = _fingerprint(event_seat_id)
            if previous is not None:
                if previous.request_fingerprint != fingerprint:
                    raise IdempotencyKeyReused
                return HoldCreationResult(
                    status_code=previous.response_status,
                    response_body=previous.response_body,
                    replayed=True,
                )

            if not await unit_of_work.holds.lock_event_seat(event_seat_id):
                raise EventSeatNotFound

            now = self._clock.now()

            if await unit_of_work.holds.has_active_reservation(event_seat_id):
                raise SeatUnavailable

            active_hold = await unit_of_work.holds.get_active_hold(event_seat_id)
            if active_hold is not None:
                if active_hold.expires_at > now:
                    raise SeatUnavailable
                await unit_of_work.holds.expire_hold(active_hold.id)

            hold = SeatHold(
                id=self._id_factory(),
                event_seat_id=event_seat_id,
                owner_id=owner_id,
                status="active",
                created_at=now,
                expires_at=now + self._hold_duration,
            )
            response_body = _hold_response_body(hold)
            await unit_of_work.holds.add_hold(hold)
            await unit_of_work.holds.flush()
            await unit_of_work.idempotency.add_record(
                id=self._id_factory(),
                owner_id=owner_id,
                operation=CREATE_HOLD_OPERATION,
                key=idempotency_key,
                request_fingerprint=fingerprint,
                hold_id=hold.id,
                reservation_id=None,
                completed_at=now,
                response_body=response_body,
            )
            await unit_of_work.commit()
            return HoldCreationResult(
                status_code=201,
                response_body=response_body,
                replayed=False,
            )


def _fingerprint(event_seat_id: UUID) -> str:
    canonical_request = json.dumps({"event_seat_id": str(event_seat_id)}, separators=(",", ":"))
    return hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()


def _hold_response_body(hold: SeatHold) -> str:
    expires_at = hold.expires_at.isoformat().replace("+00:00", "Z")
    response = {
        "id": str(hold.id),
        "event_seat_id": str(hold.event_seat_id),
        "status": "active",
        "expires_at": expires_at,
    }
    return json.dumps(response, separators=(",", ":"))
