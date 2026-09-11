from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from seatsafe.api.dependencies import get_seat_query_service
from seatsafe.api.problem_details import ProblemException
from seatsafe.application.seats import SeatQueryService
from seatsafe.domain.seats import EventNotFound

router = APIRouter(prefix="/v1/events", tags=["seats"])


class EventSeatResponse(BaseModel):
    event_seat_id: UUID
    section: str
    row: str
    number: str
    price_cents: int
    status: Literal["available", "held", "reserved"]


class EventSeatListResponse(BaseModel):
    event_id: UUID
    seats: list[EventSeatResponse]


@router.get("/{event_id}/seats", response_model=EventSeatListResponse)
async def list_event_seats(
    event_id: UUID,
    service: Annotated[SeatQueryService, Depends(get_seat_query_service)],
) -> EventSeatListResponse:
    try:
        seats = await service.list_event_seats(event_id)
    except EventNotFound as error:
        raise ProblemException(
            status=404,
            code="resource_not_found",
            title="Event not found",
            detail="The requested event does not exist.",
        ) from error

    return EventSeatListResponse(
        event_id=event_id,
        seats=[EventSeatResponse.model_validate(seat, from_attributes=True) for seat in seats],
    )
