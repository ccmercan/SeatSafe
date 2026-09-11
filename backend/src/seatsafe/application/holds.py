from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Protocol, Self
from uuid import UUID

from seatsafe.domain.holds import EventSeatNotFound, SeatHold, SeatUnavailable


class Clock(Protocol):
    def now(self) -> datetime: ...


class HoldRepository(Protocol):
    async def lock_event_seat(self, event_seat_id: UUID) -> bool: ...

    async def has_active_reservation(self, event_seat_id: UUID) -> bool: ...

    async def get_active_hold(self, event_seat_id: UUID) -> SeatHold | None: ...

    async def expire_hold(self, hold_id: UUID) -> None: ...

    async def add_hold(self, hold: SeatHold) -> None: ...


class HoldUnitOfWork(Protocol):
    holds: HoldRepository

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

    async def create_hold(self, *, event_seat_id: UUID, owner_id: UUID) -> SeatHold:
        now = self._clock.now()

        async with self._unit_of_work_factory() as unit_of_work:
            if not await unit_of_work.holds.lock_event_seat(event_seat_id):
                raise EventSeatNotFound

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
            await unit_of_work.holds.add_hold(hold)
            await unit_of_work.commit()
            return hold
