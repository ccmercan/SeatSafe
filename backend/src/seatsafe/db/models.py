from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRecord(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)


class VenueRecord(Base):
    __tablename__ = "venues"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class EventRecord(Base):
    __tablename__ = "events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    venue_id: Mapped[UUID] = mapped_column(ForeignKey("venues.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SeatRecord(Base):
    __tablename__ = "seats"
    __table_args__ = (
        Index(
            "uq_seats_venue_location",
            "venue_id",
            "section",
            "row_label",
            "seat_number",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    venue_id: Mapped[UUID] = mapped_column(ForeignKey("venues.id"), nullable=False)
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    row_label: Mapped[str] = mapped_column(String(20), nullable=False)
    seat_number: Mapped[str] = mapped_column(String(20), nullable=False)


class EventSeatRecord(Base):
    __tablename__ = "event_seats"
    __table_args__ = (
        CheckConstraint("price_cents >= 0", name="ck_event_seats_nonnegative_price"),
        Index("uq_event_seats_event_seat", "event_id", "seat_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"), nullable=False)
    seat_id: Mapped[UUID] = mapped_column(ForeignKey("seats.id"), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)


class SeatHoldRecord(Base):
    __tablename__ = "seat_holds"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'confirmed', 'released', 'expired')",
            name="ck_seat_holds_status",
        ),
        CheckConstraint("expires_at > created_at", name="ck_seat_holds_expiry_after_creation"),
        Index(
            "uq_seat_holds_one_active_per_event_seat",
            "event_seat_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_seat_id: Mapped[UUID] = mapped_column(ForeignKey("event_seats.id"), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReservationRecord(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'cancelled')",
            name="ck_reservations_status",
        ),
        CheckConstraint(
            "(status = 'active' AND cancelled_at IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL)",
            name="ck_reservations_cancellation_state",
        ),
        Index(
            "uq_reservations_one_active_per_event_seat",
            "event_seat_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    event_seat_id: Mapped[UUID] = mapped_column(ForeignKey("event_seats.id"), nullable=False)
    hold_id: Mapped[UUID] = mapped_column(ForeignKey("seat_holds.id"), nullable=False, unique=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        CheckConstraint(
            "response_status BETWEEN 200 AND 599",
            name="ck_idempotency_response_status",
        ),
        Index(
            "uq_idempotency_owner_operation_key",
            "owner_id",
            "operation",
            "idempotency_key",
            unique=True,
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    reservation_id: Mapped[UUID] = mapped_column(ForeignKey("reservations.id"), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    response_body: Mapped[str] = mapped_column(Text, nullable=False)
