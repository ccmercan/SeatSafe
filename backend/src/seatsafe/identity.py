from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends

from seatsafe.config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Trusted identity supplied by the server, not by request data."""

    id: UUID


def get_current_user(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentUser:
    return CurrentUser(id=settings.demo_user_id)
