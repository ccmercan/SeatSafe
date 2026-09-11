from functools import lru_cache
from typing import Literal
from uuid import UUID

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Server-owned configuration loaded from SeatSafe environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="SEATSAFE_",
        extra="ignore",
    )

    app_name: str = "SeatSafe API"
    environment: Literal["local", "test", "production"] = "local"
    demo_user_id: UUID = UUID("00000000-0000-4000-8000-000000000001")
    hold_duration_seconds: int = Field(default=300, ge=1, le=3600)
    database_url: str = "postgresql+asyncpg://seatsafe:seatsafe@localhost:54329/seatsafe_test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
