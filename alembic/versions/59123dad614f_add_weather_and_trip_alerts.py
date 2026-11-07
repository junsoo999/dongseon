"""add weather and trip alerts; drop stored Google hours text from itinerary items

Revision ID: 59123dad614f
Revises: b8b673824e40
Create Date: 2026-11-07 23:23:19.767579

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "59123dad614f"
down_revision: str | Sequence[str] | None = "b8b673824e40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Earlier versions saved Google opening times in the item's hours label; keep only the source name.
_GOOGLE_LABELS = {"google_special": "Google 특별 영업", "google_regular": "Google"}


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "weather",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("city_key", sa.String(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("city_key", "day", "kind", name="uq_weather_city_day_kind"),
    )
    op.create_table(
        "trip_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trip_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("itinerary_id", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["itinerary_id"], ["itineraries.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trip_id"], ["trips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("trip_alerts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_trip_alerts_trip_id"), ["trip_id"], unique=False)

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, warnings_json FROM itinerary_items WHERE warnings_json IS NOT NULL"))
    for item_id, raw in rows.fetchall():
        data = json.loads(raw)
        label = _GOOGLE_LABELS.get(data.get("hours_source") or "")
        if label and data.get("hours") != label:
            data["hours"] = label
            conn.execute(
                sa.text("UPDATE itinerary_items SET warnings_json = :w WHERE id = :id"),
                {"w": json.dumps(data, ensure_ascii=False), "id": item_id},
            )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("trip_alerts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_trip_alerts_trip_id"))

    op.drop_table("trip_alerts")
    op.drop_table("weather")
