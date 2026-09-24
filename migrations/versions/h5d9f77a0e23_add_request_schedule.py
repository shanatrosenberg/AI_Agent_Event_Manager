"""Add schedule and event_id to talk requests

Revision ID: h5d9f77a0e23
Revises: g4c8e66f9d12
Create Date: 2026-09-24 14:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "h5d9f77a0e23"
down_revision = "g4c8e66f9d12"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("talk_requests", sa.Column("date", sa.String(length=64), nullable=True))
    op.add_column("talk_requests", sa.Column("start_time", sa.String(length=8), nullable=True))
    op.add_column("talk_requests", sa.Column("end_time", sa.String(length=8), nullable=True))
    op.add_column("talk_requests", sa.Column("capacity", sa.Integer(), nullable=True))
    op.add_column("talk_requests", sa.Column("event_id", sa.String(length=36), nullable=True))


def downgrade():
    op.drop_column("talk_requests", "event_id")
    op.drop_column("talk_requests", "capacity")
    op.drop_column("talk_requests", "end_time")
    op.drop_column("talk_requests", "start_time")
    op.drop_column("talk_requests", "date")
