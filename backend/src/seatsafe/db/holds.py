from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from seatsafe.db.models import EventSeatRecord, ReservationRecord, SeatHoldRecord
from seatsafe.domain.holds import SeatHold


class SqlAlchemyHoldRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_event_seat(self, event_seat_id: UUID) -> bool:
        statement = (
            select(EventSeatRecord.id).where(EventSeatRecord.id == event_seat_id).with_for_update()
        )
        return (await self._session.scalar(statement)) is not None

    async def has_active_reservation(self, event_seat_id: UUID) -> bool:
        statement = select(ReservationRecord.id).where(
            ReservationRecord.event_seat_id == event_seat_id,
            ReservationRecord.status == "active",
        )
        return (await self._session.scalar(statement)) is not None

    async def get_active_hold(self, event_seat_id: UUID) -> SeatHold | None:
        statement = select(SeatHoldRecord).where(
            SeatHoldRecord.event_seat_id == event_seat_id,
            SeatHoldRecord.status == "active",
        )
        record = await self._session.scalar(statement)
        if record is None:
            return None
        return SeatHold(
            id=record.id,
            event_seat_id=record.event_seat_id,
            owner_id=record.owner_id,
            status=record.status,
            created_at=record.created_at,
            expires_at=record.expires_at,
        )

    async def expire_hold(self, hold_id: UUID) -> None:
        await self._session.execute(
            update(SeatHoldRecord)
            .where(SeatHoldRecord.id == hold_id, SeatHoldRecord.status == "active")
            .values(status="expired")
        )

    async def add_hold(self, hold: SeatHold) -> None:
        self._session.add(
            SeatHoldRecord(
                id=hold.id,
                event_seat_id=hold.event_seat_id,
                owner_id=hold.owner_id,
                status=hold.status,
                created_at=hold.created_at,
                expires_at=hold.expires_at,
            )
        )


class SqlAlchemyHoldUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self.holds: SqlAlchemyHoldRepository

    async def __aenter__(self) -> "SqlAlchemyHoldUnitOfWork":
        self._session = self._session_factory()
        await self._session.begin()
        self.holds = SqlAlchemyHoldRepository(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        if self._session is None:
            return
        if self._session.in_transaction():
            await self._session.rollback()
        await self._session.close()

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("The unit of work has not been entered.")
        await self._session.commit()
