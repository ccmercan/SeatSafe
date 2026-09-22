import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from seatsafe.application.holds import HoldService
from seatsafe.application.reservations import ReservationService
from seatsafe.application.seats import SeatQueryService
from seatsafe.config import Settings
from seatsafe.db.demo_seed import (
    DEMO_EVENT_ID,
    DEMO_EVENT_SEAT_IDS,
    DEMO_USER_ID,
    seed_demo_database,
)
from seatsafe.db.holds import SqlAlchemyHoldUnitOfWork, SqlAlchemyReservationRepository
from seatsafe.db.models import IdempotencyRecord
from seatsafe.db.safety import require_test_database
from seatsafe.db.seats import SqlAlchemySeatQueryRepository
from seatsafe.db.session import create_database_engine, create_session_factory
from seatsafe.domain.holds import HoldNotActive, SeatHold, SeatUnavailable

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def migrated_database() -> None:
    settings = Settings(environment="test")
    require_test_database(settings)
    _upgrade_database()


@pytest.mark.asyncio
async def test_initial_migration_creates_expected_tables(migrated_database: None) -> None:
    settings = Settings(environment="test")
    engine = create_database_engine(settings)

    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
            )
            table_names = set(result.scalars())
    finally:
        await engine.dispose()

    assert {
        "alembic_version",
        "event_seats",
        "events",
        "idempotency_records",
        "reservations",
        "seat_holds",
        "seats",
        "users",
        "venues",
    } <= table_names


@pytest.mark.asyncio
async def test_database_rejects_two_active_holds_for_one_event_seat(
    migrated_database: None,
) -> None:
    settings = Settings(environment="test")
    engine = create_database_engine(settings)
    ids = _FixtureIds()
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)

    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE idempotency_records, reservations, seat_holds, event_seats, "
                    "events, seats, venues, users"
                )
            )
            await _seed_event_seat(connection, ids, now)
            await connection.execute(
                text(
                    "INSERT INTO seat_holds "
                    "(id, event_seat_id, owner_id, status, created_at, expires_at) "
                    "VALUES (:id, :event_seat_id, :owner_id, 'active', :created_at, :expires_at)"
                ),
                {
                    "id": ids.first_hold,
                    "event_seat_id": ids.event_seat,
                    "owner_id": ids.user,
                    "created_at": now,
                    "expires_at": now + timedelta(minutes=5),
                },
            )

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO seat_holds "
                        "(id, event_seat_id, owner_id, status, created_at, expires_at) "
                        "VALUES (:id, :event_seat_id, :owner_id, 'active', "
                        ":created_at, :expires_at)"
                    ),
                    {
                        "id": ids.second_hold,
                        "event_seat_id": ids.event_seat,
                        "owner_id": ids.user,
                        "created_at": now,
                        "expires_at": now + timedelta(minutes=5),
                    },
                )

        async with engine.connect() as connection:
            active_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM seat_holds "
                    "WHERE event_seat_id = :event_seat_id AND status = 'active'"
                ),
                {"event_seat_id": ids.event_seat},
            )
    finally:
        await engine.dispose()

    assert active_count == 1


@pytest.mark.asyncio
async def test_hold_service_creates_one_hold_and_rejects_the_next(
    migrated_database: None,
) -> None:
    settings = Settings(environment="test")
    engine = create_database_engine(settings)
    ids = _FixtureIds()
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
    session_factory = create_session_factory(engine)
    generated_ids = iter((ids.first_hold, ids.second_hold))
    service = HoldService(
        unit_of_work_factory=lambda: SqlAlchemyHoldUnitOfWork(session_factory),
        clock=_FixedClock(now),
        id_factory=lambda: next(generated_ids),
        hold_duration=timedelta(minutes=5),
    )

    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE idempotency_records, reservations, seat_holds, event_seats, "
                    "events, seats, venues, users"
                )
            )
            await _seed_event_seat(connection, ids, now)

        hold = await service.create_hold(event_seat_id=ids.event_seat, owner_id=ids.user)

        with pytest.raises(SeatUnavailable):
            await service.create_hold(event_seat_id=ids.event_seat, owner_id=ids.user)

        async with engine.connect() as connection:
            active_count = await connection.scalar(
                text("SELECT count(*) FROM seat_holds WHERE status = 'active'")
            )
    finally:
        await engine.dispose()

    assert hold.id == ids.first_hold
    assert hold.expires_at == now + timedelta(minutes=5)
    assert active_count == 1


@pytest.mark.asyncio
async def test_demo_seed_and_seat_query_report_ordered_database_state(
    migrated_database: None,
) -> None:
    settings = Settings(environment="test")
    await seed_demo_database(settings)
    await seed_demo_database(settings)
    engine = create_database_engine(settings)
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)

    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO seat_holds "
                    "(id, event_seat_id, owner_id, status, created_at, expires_at) VALUES "
                    "(:active_id, :active_seat_id, :owner_id, 'active', :created_at, :expires_at), "
                    "(:confirmed_id, :confirmed_seat_id, :owner_id, 'confirmed', "
                    ":created_at, :expires_at)"
                ),
                {
                    "active_id": UUID("00000000-0000-4000-8000-000000000050"),
                    "active_seat_id": DEMO_EVENT_SEAT_IDS[0],
                    "confirmed_id": UUID("00000000-0000-4000-8000-000000000051"),
                    "confirmed_seat_id": DEMO_EVENT_SEAT_IDS[1],
                    "owner_id": _FixtureIds.user,
                    "created_at": now,
                    "expires_at": now + timedelta(minutes=5),
                },
            )
            await connection.execute(
                text(
                    "INSERT INTO reservations "
                    "(id, event_seat_id, hold_id, owner_id, status, confirmed_at) "
                    "VALUES (:id, :event_seat_id, :hold_id, :owner_id, 'active', :confirmed_at)"
                ),
                {
                    "id": UUID("00000000-0000-4000-8000-000000000060"),
                    "event_seat_id": DEMO_EVENT_SEAT_IDS[1],
                    "hold_id": UUID("00000000-0000-4000-8000-000000000051"),
                    "owner_id": _FixtureIds.user,
                    "confirmed_at": now,
                },
            )

        service = SeatQueryService(
            repository=SqlAlchemySeatQueryRepository(create_session_factory(engine)),
            clock=_FixedClock(now),
        )
        seats = await service.list_event_seats(DEMO_EVENT_ID)
    finally:
        await engine.dispose()

    assert [seat.event_seat_id for seat in seats] == list(DEMO_EVENT_SEAT_IDS)
    assert [seat.number for seat in seats] == ["1", "2", "3"]
    assert [seat.status for seat in seats] == ["held", "reserved", "available"]


@pytest.mark.asyncio
async def test_simultaneous_same_key_confirmation_replays_one_result(
    migrated_database: None,
) -> None:
    settings = Settings(environment="test")
    await seed_demo_database(settings)
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
    hold_id = UUID("00000000-0000-4000-8000-000000000070")
    reservation_id = UUID("00000000-0000-4000-8000-000000000071")
    idempotency_id = UUID("00000000-0000-4000-8000-000000000072")

    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO seat_holds "
                    "(id, event_seat_id, owner_id, status, created_at, expires_at) "
                    "VALUES (:id, :event_seat_id, :owner_id, 'active', :created_at, :expires_at)"
                ),
                {
                    "id": hold_id,
                    "event_seat_id": DEMO_EVENT_SEAT_IDS[0],
                    "owner_id": _FixtureIds.user,
                    "created_at": now,
                    "expires_at": now + timedelta(minutes=5),
                },
            )

        first_service = _reservation_service(session_factory, now, reservation_id, idempotency_id)
        second_service = _reservation_service(session_factory, now, reservation_id, idempotency_id)
        results = await asyncio.gather(
            first_service.confirm(
                hold_id=hold_id,
                owner_id=_FixtureIds.user,
                idempotency_key="parallel-key",
            ),
            second_service.confirm(
                hold_id=hold_id,
                owner_id=_FixtureIds.user,
                idempotency_key="parallel-key",
            ),
        )

        async with engine.connect() as connection:
            reservation_count = await connection.scalar(text("SELECT count(*) FROM reservations"))
            idempotency_count = await connection.scalar(
                text("SELECT count(*) FROM idempotency_records")
            )
            hold_status = await connection.scalar(
                text("SELECT status FROM seat_holds WHERE id = :id"), {"id": hold_id}
            )
    finally:
        await engine.dispose()

    assert sorted(result.replayed for result in results) == [False, True]
    assert results[0].response_body == results[1].response_body
    assert reservation_count == 1
    assert idempotency_count == 1
    assert hold_status == "confirmed"


@pytest.mark.asyncio
async def test_simultaneous_different_keys_cannot_confirm_one_hold_twice(
    migrated_database: None,
) -> None:
    settings = Settings(environment="test")
    await seed_demo_database(settings)
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
    hold_id = UUID("00000000-0000-4000-8000-000000000070")
    reservation_id = UUID("00000000-0000-4000-8000-000000000071")
    idempotency_id = UUID("00000000-0000-4000-8000-000000000072")

    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO seat_holds "
                    "(id, event_seat_id, owner_id, status, created_at, expires_at) "
                    "VALUES (:id, :event_seat_id, :owner_id, 'active', :created_at, :expires_at)"
                ),
                {
                    "id": hold_id,
                    "event_seat_id": DEMO_EVENT_SEAT_IDS[0],
                    "owner_id": _FixtureIds.user,
                    "created_at": now,
                    "expires_at": now + timedelta(minutes=5),
                },
            )

        first_service = _reservation_service(session_factory, now, reservation_id, idempotency_id)
        second_service = _reservation_service(
            session_factory,
            now,
            UUID("00000000-0000-4000-8000-000000000073"),
            UUID("00000000-0000-4000-8000-000000000074"),
        )
        results = await asyncio.gather(
            first_service.confirm(
                hold_id=hold_id,
                owner_id=_FixtureIds.user,
                idempotency_key="parallel-key-a",
            ),
            second_service.confirm(
                hold_id=hold_id,
                owner_id=_FixtureIds.user,
                idempotency_key="parallel-key-b",
            ),
            return_exceptions=True,
        )

        async with engine.connect() as connection:
            reservation_count = await connection.scalar(text("SELECT count(*) FROM reservations"))
    finally:
        await engine.dispose()

    assert sum(not isinstance(result, BaseException) for result in results) == 1
    assert sum(isinstance(result, HoldNotActive) for result in results) == 1
    assert reservation_count == 1


@pytest.mark.asyncio
async def test_simultaneous_hold_requests_create_one_winner_that_can_be_confirmed(
    migrated_database: None,
) -> None:
    settings = Settings(environment="test")
    await seed_demo_database(settings)
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
    first_hold_id = UUID("00000000-0000-4000-8000-000000000080")
    second_hold_id = UUID("00000000-0000-4000-8000-000000000081")
    second_owner_id = UUID("00000000-0000-4000-8000-000000000002")

    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("INSERT INTO users (id, display_name) VALUES (:id, 'Second User')"),
                {"id": second_owner_id},
            )

        first_service = _hold_service(session_factory, now, first_hold_id)
        second_service = _hold_service(session_factory, now, second_hold_id)
        outcomes = await asyncio.gather(
            first_service.create_hold(event_seat_id=DEMO_EVENT_SEAT_IDS[0], owner_id=DEMO_USER_ID),
            second_service.create_hold(
                event_seat_id=DEMO_EVENT_SEAT_IDS[0], owner_id=second_owner_id
            ),
            return_exceptions=True,
        )

        winning_hold = next(outcome for outcome in outcomes if isinstance(outcome, SeatHold))
        reservation_service = _reservation_service(
            session_factory,
            now,
            UUID("00000000-0000-4000-8000-000000000082"),
            UUID("00000000-0000-4000-8000-000000000083"),
        )
        confirmation = await reservation_service.confirm(
            hold_id=winning_hold.id,
            owner_id=winning_hold.owner_id,
            idempotency_key="winning-hold-confirmation",
        )

        async with engine.connect() as connection:
            hold_count = await connection.scalar(text("SELECT count(*) FROM seat_holds"))
            active_hold_count = await connection.scalar(
                text("SELECT count(*) FROM seat_holds WHERE status = 'active'")
            )
            reservation_count = await connection.scalar(text("SELECT count(*) FROM reservations"))
            reservation_hold_id = await connection.scalar(
                text("SELECT hold_id FROM reservations LIMIT 1")
            )
            final_hold_status = await connection.scalar(
                text("SELECT status FROM seat_holds WHERE id = :id"),
                {"id": winning_hold.id},
            )
    finally:
        await engine.dispose()

    assert sum(isinstance(outcome, SeatHold) for outcome in outcomes) == 1
    assert sum(isinstance(outcome, SeatUnavailable) for outcome in outcomes) == 1
    assert confirmation.status_code == 201
    assert hold_count == 1
    assert active_hold_count == 0
    assert reservation_count == 1
    assert reservation_hold_id == winning_hold.id
    assert final_hold_status == "confirmed"


@pytest.mark.asyncio
async def test_confirmation_rolls_back_all_writes_when_idempotency_insert_violates_constraint(
    migrated_database: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(environment="test")
    await seed_demo_database(settings)
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)
    hold_id = UUID("00000000-0000-4000-8000-000000000090")
    original_add_idempotency_record = SqlAlchemyReservationRepository.add_idempotency_record

    async def add_invalid_idempotency_record(
        repository: SqlAlchemyReservationRepository,
        *,
        id: UUID,
        owner_id: UUID,
        key: str,
        request_fingerprint: str,
        reservation_id: UUID,
        completed_at: datetime,
        response_body: str,
    ) -> None:
        await original_add_idempotency_record(
            repository,
            id=id,
            owner_id=owner_id,
            key=key,
            request_fingerprint=request_fingerprint,
            reservation_id=reservation_id,
            completed_at=completed_at,
            response_body=response_body,
        )
        pending_record = next(
            record for record in repository._session.new if isinstance(record, IdempotencyRecord)
        )
        # PostgreSQL's response_status check allows 200–599; 199 forces a real DB error.
        pending_record.response_status = 199

    monkeypatch.setattr(
        SqlAlchemyReservationRepository,
        "add_idempotency_record",
        add_invalid_idempotency_record,
    )

    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO seat_holds "
                    "(id, event_seat_id, owner_id, status, created_at, expires_at) "
                    "VALUES (:id, :event_seat_id, :owner_id, 'active', :created_at, :expires_at)"
                ),
                {
                    "id": hold_id,
                    "event_seat_id": DEMO_EVENT_SEAT_IDS[0],
                    "owner_id": DEMO_USER_ID,
                    "created_at": now,
                    "expires_at": now + timedelta(minutes=5),
                },
            )

        service = _reservation_service(
            session_factory,
            now,
            UUID("00000000-0000-4000-8000-000000000091"),
            UUID("00000000-0000-4000-8000-000000000092"),
        )
        with pytest.raises(IntegrityError, match="ck_idempotency_response_status"):
            await service.confirm(
                hold_id=hold_id,
                owner_id=DEMO_USER_ID,
                idempotency_key="rollback-after-reservation-flush",
            )

        async with engine.connect() as connection:
            hold_status = await connection.scalar(
                text("SELECT status FROM seat_holds WHERE id = :id"), {"id": hold_id}
            )
            reservation_count = await connection.scalar(text("SELECT count(*) FROM reservations"))
            idempotency_count = await connection.scalar(
                text("SELECT count(*) FROM idempotency_records")
            )
    finally:
        await engine.dispose()

    assert hold_status == "active"
    assert reservation_count == 0
    assert idempotency_count == 0


class _FixtureIds:
    user = UUID("00000000-0000-4000-8000-000000000001")
    venue = UUID("00000000-0000-4000-8000-000000000010")
    event = UUID("00000000-0000-4000-8000-000000000020")
    seat = UUID("00000000-0000-4000-8000-000000000030")
    event_seat = UUID("00000000-0000-4000-8000-000000000040")
    first_hold = UUID("00000000-0000-4000-8000-000000000050")
    second_hold = UUID("00000000-0000-4000-8000-000000000051")


class _FixedClock:
    def __init__(self, value: datetime) -> None:
        self._value = value

    def now(self) -> datetime:
        return self._value


def _reservation_service(
    session_factory,
    now: datetime,
    reservation_id: UUID,
    idempotency_id: UUID,
) -> ReservationService:
    generated_ids = iter((reservation_id, idempotency_id))
    return ReservationService(
        unit_of_work_factory=lambda: SqlAlchemyHoldUnitOfWork(session_factory),
        clock=_FixedClock(now),
        id_factory=lambda: next(generated_ids),
    )


def _hold_service(
    session_factory,
    now: datetime,
    hold_id: UUID,
) -> HoldService:
    return HoldService(
        unit_of_work_factory=lambda: SqlAlchemyHoldUnitOfWork(session_factory),
        clock=_FixedClock(now),
        id_factory=lambda: hold_id,
        hold_duration=timedelta(minutes=5),
    )


async def _seed_event_seat(connection: object, ids: _FixtureIds, now: datetime) -> None:
    await connection.execute(
        text("INSERT INTO users (id, display_name) VALUES (:id, 'Demo User')"),
        {"id": ids.user},
    )
    await connection.execute(
        text("INSERT INTO venues (id, name) VALUES (:id, 'Test Hall')"),
        {"id": ids.venue},
    )
    await connection.execute(
        text(
            "INSERT INTO events (id, venue_id, title, starts_at) "
            "VALUES (:id, :venue_id, 'Test Event', :starts_at)"
        ),
        {"id": ids.event, "venue_id": ids.venue, "starts_at": now + timedelta(days=1)},
    )
    await connection.execute(
        text(
            "INSERT INTO seats (id, venue_id, section, row_label, seat_number) "
            "VALUES (:id, :venue_id, 'Main', 'A', '1')"
        ),
        {"id": ids.seat, "venue_id": ids.venue},
    )
    await connection.execute(
        text(
            "INSERT INTO event_seats (id, event_id, seat_id, price_cents) "
            "VALUES (:id, :event_id, :seat_id, 2500)"
        ),
        {"id": ids.event_seat, "event_id": ids.event, "seat_id": ids.seat},
    )


def _upgrade_database() -> None:
    backend_directory = Path(__file__).resolve().parents[2]
    alembic_config = Config(str(backend_directory / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(backend_directory / "migrations"))
    command.upgrade(alembic_config, "head")
