from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel
from starlette.responses import Response

from seatsafe.api.dependencies import get_reservation_service
from seatsafe.api.problem_details import ProblemException
from seatsafe.application.reservations import ReservationService
from seatsafe.domain.holds import (
    HoldExpired,
    HoldNotActive,
    HoldNotFound,
    HoldOwnerMismatch,
    IdempotencyKeyReused,
    SeatUnavailable,
)
from seatsafe.identity import CurrentUser, get_current_user

router = APIRouter(prefix="/v1/reservations", tags=["reservations"])


class ConfirmReservationRequest(BaseModel):
    hold_id: UUID


class ReservationResponse(BaseModel):
    id: UUID
    hold_id: UUID
    event_seat_id: UUID
    status: Literal["active"]
    confirmed_at: datetime


@router.post(
    "",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_reservation(
    request_body: ConfirmReservationRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)],
) -> Response:
    try:
        result = await service.confirm(
            hold_id=request_body.hold_id,
            owner_id=current_user.id,
            idempotency_key=idempotency_key,
        )
    except HoldNotFound as error:
        raise ProblemException(
            status=404,
            code="resource_not_found",
            title="Hold not found",
            detail="The requested hold does not exist.",
        ) from error
    except HoldOwnerMismatch as error:
        raise ProblemException(
            status=403,
            code="hold_owner_mismatch",
            title="Hold belongs to another user",
            detail="Only the owner of this hold can confirm it.",
        ) from error
    except HoldExpired as error:
        raise ProblemException(
            status=409,
            code="hold_expired",
            title="Hold expired",
            detail="The hold expired before it could be confirmed.",
        ) from error
    except (HoldNotActive, SeatUnavailable) as error:
        raise ProblemException(
            status=409,
            code="seat_unavailable",
            title="Hold cannot be confirmed",
            detail="The hold is no longer eligible for confirmation.",
        ) from error
    except IdempotencyKeyReused as error:
        raise ProblemException(
            status=409,
            code="idempotency_key_reused",
            title="Idempotency key already used",
            detail="Use a new key for a different confirmation request.",
        ) from error

    return Response(
        content=result.response_body,
        status_code=result.status_code,
        media_type="application/json",
    )
