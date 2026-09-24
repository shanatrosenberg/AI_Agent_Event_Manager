"""Add speaker_id to events

Revision ID: d8e3b12c9a44
Revises: c4f2a91e7b10
Create Date: 2026-09-24 13:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d8e3b12c9a44"
down_revision = "c4f2a91e7b10"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("events", sa.Column("speaker_id", sa.String(length=64), nullable=True))
    op.create_foreign_key(
        "fk_events_speaker_id_speakers",
        "events",
        "speakers",
        ["speaker_id"],
        ["id"],
    )


def downgrade():
    op.drop_constraint("fk_events_speaker_id_speakers", "events", type_="foreignkey")
    op.drop_column("events", "speaker_id")
