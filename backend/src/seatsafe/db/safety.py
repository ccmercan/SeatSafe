from sqlalchemy.engine import make_url

from seatsafe.config import Settings


class UnsafeDatabaseTarget(RuntimeError):
    pass


def require_test_database(settings: Settings) -> None:
    """Refuse destructive test setup unless both configuration signals are explicit."""

    database_name = make_url(settings.database_url).database or ""
    if settings.environment != "test" or not database_name.endswith("_test"):
        raise UnsafeDatabaseTarget(
            "Database reset requires environment='test' and a database name ending in '_test'."
        )
