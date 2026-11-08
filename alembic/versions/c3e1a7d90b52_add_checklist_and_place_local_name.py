"""add checklist items and places.local_name (filled from accepted AI place research)

Revision ID: c3e1a7d90b52
Revises: 59123dad614f
Create Date: 2026-11-08 10:00:00.000000

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e1a7d90b52"
down_revision: str | Sequence[str] | None = "59123dad614f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "checklist_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trip_id", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("checklist_items", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_checklist_items_trip_id"), ["trip_id"], unique=False)
    with op.batch_alter_table("places", schema=None) as batch_op:
        batch_op.add_column(sa.Column("local_name", sa.String(), nullable=True))

    # Accepted AI place suggestions carried a local-language name; keep it on the place they became.
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT google_place_id, payload_json FROM ai_suggestions "
            "WHERE kind = 'place' AND status = 'accepted' AND google_place_id IS NOT NULL"
        )
    ).fetchall()
    for gid, payload in rows:
        name_local = (json.loads(payload or "{}").get("name_local") or "").strip()
        if name_local:
            conn.execute(
                sa.text("UPDATE places SET local_name = :n WHERE google_place_id = :g AND local_name IS NULL"),
                {"n": name_local, "g": gid},
            )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("places", schema=None) as batch_op:
        batch_op.drop_column("local_name")
    with op.batch_alter_table("checklist_items", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_checklist_items_trip_id"))
    op.drop_table("checklist_items")
