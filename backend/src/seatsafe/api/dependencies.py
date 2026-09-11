from collections.abc import Callable
from datetime import timedelta
from functools import partial
from typing import Annotated

from fastapi import Depends, Request

from seatsafe.application.holds import HoldService, HoldUnitOfWork
from seatsafe.application.seats import SeatQueryService
from seatsafe.config import Settings, get_settings
from seatsafe.db.holds import SqlAlchemyHoldUnitOfWork
from seatsafe.db.seats import SqlAlchemySeatQueryRepository
from seatsafe.runtime import SystemClock, generate_id


def get_hold_service(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HoldService:
    unit_of_work_factory: Callable[[], HoldUnitOfWork] = partial(
        SqlAlchemyHoldUnitOfWork,
        request.app.state.session_factory,
    )
    return HoldService(
        unit_of_work_factory=unit_of_work_factory,
        clock=SystemClock(),
        id_factory=generate_id,
        hold_duration=timedelta(seconds=settings.hold_duration_seconds),
    )


def get_seat_query_service(request: Request) -> SeatQueryService:
    return SeatQueryService(
        repository=SqlAlchemySeatQueryRepository(request.app.state.session_factory),
        clock=SystemClock(),
    )
