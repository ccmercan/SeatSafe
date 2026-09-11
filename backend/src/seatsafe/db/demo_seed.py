import asyncio
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text

from seatsafe.config import Settings
from seatsafe.db.safety import require_test_database
from seatsafe.db.session import create_database_engine

DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
DEMO_VENUE_ID = UUID("00000000-0000-4000-8000-000000000010")
DEMO_EVENT_ID = UUID("00000000-0000-4000-8000-000000000020")
DEMO_SEAT_IDS = (
    UUID("00000000-0000-4000-8000-000000000030"),
    UUID("00000000-0000-4000-8000-000000000031"),
    UUID("00000000-0000-4000-8000-000000000032"),
)
DEMO_EVENT_SEAT_IDS = (
    UUID("00000000-0000-4000-8000-000000000040"),
    UUID("00000000-0000-4000-8000-000000000041"),
    UUID("00000000-0000-4000-8000-000000000042"),
)
DEMO_EVENT_START = datetime(2030, 6, 15, 19, 0, tzinfo=UTC)


async def seed_demo_database(settings: Settings) -> None:
    """Replace disposable test data with one stable manual-demo scenario."""

    require_test_database(settings)
    engine = create_database_engine(settings)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE idempotency_records, reservations, seat_holds, event_seats, "
                    "events, seats, venues, users"
                )
            )
            await connection.execute(
                text("INSERT INTO users (id, display_name) VALUES (:id, :display_name)"),
                {"id": DEMO_USER_ID, "display_name": "Demo User"},
            )
            await connection.execute(
                text("INSERT INTO venues (id, name) VALUES (:id, :name)"),
                {"id": DEMO_VENUE_ID, "name": "SeatSafe Test Hall"},
            )
            await connection.execute(
                text(
                    "INSERT INTO events (id, venue_id, title, starts_at) "
                    "VALUES (:id, :venue_id, :title, :starts_at)"
                ),
                {
                    "id": DEMO_EVENT_ID,
                    "venue_id": DEMO_VENUE_ID,
                    "title": "The Deterministic Show",
                    "starts_at": DEMO_EVENT_START,
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO seats "
                    "(id, venue_id, section, row_label, seat_number) "
                    "VALUES (:id, :venue_id, :section, :row_label, :seat_number)"
                ),
                [
                    {
                        "id": seat_id,
                        "venue_id": DEMO_VENUE_ID,
                        "section": "Main",
                        "row_label": "A",
                        "seat_number": str(index),
                    }
                    for index, seat_id in enumerate(DEMO_SEAT_IDS, start=1)
                ],
            )
            await connection.execute(
                text(
                    "INSERT INTO event_seats (id, event_id, seat_id, price_cents) "
                    "VALUES (:id, :event_id, :seat_id, :price_cents)"
                ),
                [
                    {
                        "id": event_seat_id,
                        "event_id": DEMO_EVENT_ID,
                        "seat_id": seat_id,
                        "price_cents": price_cents,
                    }
                    for event_seat_id, seat_id, price_cents in zip(
                        DEMO_EVENT_SEAT_IDS,
                        DEMO_SEAT_IDS,
                        (2500, 2750, 3000),
                        strict=True,
                    )
                ],
            )
    finally:
        await engine.dispose()


async def _main() -> None:
    settings = Settings()
    await seed_demo_database(settings)
    print(f"Seeded demo event {DEMO_EVENT_ID} with {len(DEMO_EVENT_SEAT_IDS)} seats.")


if __name__ == "__main__":
    asyncio.run(_main())
