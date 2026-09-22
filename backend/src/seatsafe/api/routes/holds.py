from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel
from starlette.responses import Response

from seatsafe.api.dependencies import get_hold_service
from seatsafe.api.problem_details import ProblemException
from seatsafe.application.holds import HoldService
from seatsafe.domain.holds import EventSeatNotFound, IdempotencyKeyReused, SeatUnavailable
from seatsafe.identity import CurrentUser, get_current_user

router = APIRouter(prefix="/v1/holds", tags=["holds"])


class CreateHoldRequest(BaseModel):
    event_seat_id: UUID


class HoldResponse(BaseModel):
    id: UUID
    event_seat_id: UUID
    status: Literal["active"]
    expires_at: datetime


@router.post("", response_model=HoldResponse, status_code=status.HTTP_201_CREATED)
async def create_hold(
    request_body: CreateHoldRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[HoldService, Depends(get_hold_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
) -> Response:
    try:
        result = await service.create_hold(
            event_seat_id=request_body.event_seat_id,
            owner_id=current_user.id,
            idempotency_key=idempotency_key,
        )
    except EventSeatNotFound as error:
        raise ProblemException(
            status=404,
            code="resource_not_found",
            title="Event seat not found",
            detail="The requested event seat does not exist.",
        ) from error
    except SeatUnavailable as error:
        raise ProblemException(
            status=409,
            code="seat_unavailable",
            title="Seat unavailable",
            detail="The selected seat cannot currently be held.",
        ) from error
    except IdempotencyKeyReused as error:
        raise ProblemException(
            status=409,
            code="idempotency_key_reused",
            title="Idempotency key already used",
            detail="Use a new key for a different hold request.",
        ) from error

    return Response(
        content=result.response_body,
        status_code=result.status_code,
        media_type="application/json",
    )
