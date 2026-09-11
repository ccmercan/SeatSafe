"""Create the initial reservation schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "venues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "seats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("venue_id", sa.Uuid(), nullable=False),
        sa.Column("section", sa.String(length=50), nullable=False),
        sa.Column("row_label", sa.String(length=20), nullable=False),
        sa.Column("seat_number", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["venue_id"], ["venues.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_seats_venue_location",
        "seats",
        ["venue_id", "section", "row_label", "seat_number"],
        unique=True,
    )
    op.create_table(
        "event_seats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("seat_id", sa.Uuid(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.CheckConstraint("price_cents >= 0", name="ck_event_seats_nonnegative_price"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["seat_id"], ["seats.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_event_seats_event_seat",
        "event_seats",
        ["event_id", "seat_id"],
        unique=True,
    )
    op.create_table(
        "seat_holds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_seat_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "expires_at > created_at",
            name="ck_seat_holds_expiry_after_creation",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'confirmed', 'released', 'expired')",
            name="ck_seat_holds_status",
        ),
        sa.ForeignKeyConstraint(["event_seat_id"], ["event_seats.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_seat_holds_one_active_per_event_seat",
        "seat_holds",
        ["event_seat_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_seat_id", sa.Uuid(), nullable=False),
        sa.Column("hold_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(status = 'active' AND cancelled_at IS NULL) OR "
            "(status = 'cancelled' AND cancelled_at IS NOT NULL)",
            name="ck_reservations_cancellation_state",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled')",
            name="ck_reservations_status",
        ),
        sa.ForeignKeyConstraint(["event_seat_id"], ["event_seats.id"]),
        sa.ForeignKeyConstraint(["hold_id"], ["seat_holds.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hold_id"),
    )
    op.create_index(
        "uq_reservations_one_active_per_event_seat",
        "reservations",
        ["event_seat_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(length=50), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "response_status BETWEEN 200 AND 599",
            name="ck_idempotency_response_status",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_idempotency_owner_operation_key",
        "idempotency_records",
        ["owner_id", "operation", "idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_idempotency_owner_operation_key", table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("uq_reservations_one_active_per_event_seat", table_name="reservations")
    op.drop_table("reservations")
    op.drop_index("uq_seat_holds_one_active_per_event_seat", table_name="seat_holds")
    op.drop_table("seat_holds")
    op.drop_index("uq_event_seats_event_seat", table_name="event_seats")
    op.drop_table("event_seats")
    op.drop_index("uq_seats_venue_location", table_name="seats")
    op.drop_table("seats")
    op.drop_table("events")
    op.drop_table("venues")
    op.drop_table("users")
