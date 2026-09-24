"""Add event start and end times

Revision ID: f2b7d55e8c01
Revises: e1a9c44b2d70
Create Date: 2026-09-24 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f2b7d55e8c01"
down_revision = "e1a9c44b2d70"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("events", sa.Column("start_time", sa.String(length=8), nullable=True))
    op.add_column("events", sa.Column("end_time", sa.String(length=8), nullable=True))


def downgrade():
    op.drop_column("events", "end_time")
    op.drop_column("events", "start_time")
