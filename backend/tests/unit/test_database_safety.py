import pytest

from seatsafe.config import Settings
from seatsafe.db.safety import UnsafeDatabaseTarget, require_test_database


def test_test_database_requires_test_environment() -> None:
    settings = Settings(
        environment="local",
        database_url="postgresql+asyncpg://localhost/seatsafe_test",
    )

    with pytest.raises(UnsafeDatabaseTarget):
        require_test_database(settings)


def test_test_database_requires_test_suffix() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://localhost/seatsafe",
    )

    with pytest.raises(UnsafeDatabaseTarget):
        require_test_database(settings)


def test_explicit_test_target_is_allowed() -> None:
    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://localhost/seatsafe_test",
    )

    require_test_database(settings)
