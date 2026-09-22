"""Support idempotent hold and reservation outcomes."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "idempotency_records",
        "reservation_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    op.add_column("idempotency_records", sa.Column("hold_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_idempotency_records_hold_id_seat_holds",
        "idempotency_records",
        "seat_holds",
        ["hold_id"],
        ["id"],
    )
    op.create_check_constraint(
        "ck_idempotency_operation_outcome",
        "idempotency_records",
        "(operation = 'create_hold' AND hold_id IS NOT NULL AND reservation_id IS NULL) "
        "OR (operation = 'confirm_reservation' AND hold_id IS NULL "
        "AND reservation_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_idempotency_operation_outcome", "idempotency_records", type_="check"
    )
    op.drop_constraint(
        "fk_idempotency_records_hold_id_seat_holds",
        "idempotency_records",
        type_="foreignkey",
    )
    op.drop_column("idempotency_records", "hold_id")
    op.alter_column(
        "idempotency_records",
        "reservation_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
