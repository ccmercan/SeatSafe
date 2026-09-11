from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from seatsafe.db.models import (
    EventRecord,
    EventSeatRecord,
    ReservationRecord,
    SeatHoldRecord,
    SeatRecord,
)


@dataclass(frozen=True, slots=True)
class SqlAlchemyEventSeatFact:
    event_seat_id: UUID
    section: str
    row: str
    number: str
    price_cents: int
    active_hold_expires_at: datetime | None
    has_active_reservation: bool


class SqlAlchemySeatQueryRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_for_event(self, event_id: UUID) -> list[SqlAlchemyEventSeatFact] | None:
        async with self._session_factory() as session:
            event_exists = await session.scalar(
                select(EventRecord.id).where(EventRecord.id == event_id)
            )
            if event_exists is None:
                return None

            active_hold_expiry = (
                select(func.max(SeatHoldRecord.expires_at))
                .where(
                    SeatHoldRecord.event_seat_id == EventSeatRecord.id,
                    SeatHoldRecord.status == "active",
                )
                .correlate(EventSeatRecord)
                .scalar_subquery()
            )
            has_active_reservation = exists(
                select(ReservationRecord.id).where(
                    ReservationRecord.event_seat_id == EventSeatRecord.id,
                    ReservationRecord.status == "active",
                )
            )
            statement = (
                select(
                    EventSeatRecord.id,
                    SeatRecord.section,
                    SeatRecord.row_label,
                    SeatRecord.seat_number,
                    EventSeatRecord.price_cents,
                    active_hold_expiry.label("active_hold_expires_at"),
                    has_active_reservation.label("has_active_reservation"),
                )
                .join(SeatRecord, SeatRecord.id == EventSeatRecord.seat_id)
                .where(EventSeatRecord.event_id == event_id)
                .order_by(SeatRecord.section, SeatRecord.row_label, SeatRecord.seat_number)
            )
            rows = (await session.execute(statement)).all()

        return [
            SqlAlchemyEventSeatFact(
                event_seat_id=row.id,
                section=row.section,
                row=row.row_label,
                number=row.seat_number,
                price_cents=row.price_cents,
                active_hold_expires_at=row.active_hold_expires_at,
                has_active_reservation=row.has_active_reservation,
            )
            for row in rows
        ]
