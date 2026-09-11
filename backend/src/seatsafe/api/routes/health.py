from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["operations"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report process health without claiming database readiness."""

    return HealthResponse(status="ok", service="seatsafe-api")
