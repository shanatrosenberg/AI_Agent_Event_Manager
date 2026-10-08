"""Add Event Sourcing metadata to stored_events

Revision ID: k9b3d12e4f67
Revises: j8a2c01d3e56
Create Date: 2026-10-08 16:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "k9b3d12e4f67"
down_revision = "j8a2c01d3e56"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stored_events") as batch_op:
        batch_op.add_column(sa.Column("aggregate_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("aggregate_type", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("occurred_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_stored_events_aggregate_id", ["aggregate_id"])
        batch_op.create_index("ix_stored_events_aggregate_type", ["aggregate_type"])


def downgrade():
    with op.batch_alter_table("stored_events") as batch_op:
        batch_op.drop_index("ix_stored_events_aggregate_type")
        batch_op.drop_index("ix_stored_events_aggregate_id")
        batch_op.drop_column("occurred_at")
        batch_op.drop_column("aggregate_type")
        batch_op.drop_column("aggregate_id")
