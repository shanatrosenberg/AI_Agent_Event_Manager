"""Add schedule fields to talk submissions

Revision ID: g4c8e66f9d12
Revises: f2b7d55e8c01
Create Date: 2026-09-24 14:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g4c8e66f9d12"
down_revision = "f2b7d55e8c01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("talk_submissions", sa.Column("date", sa.String(length=64), nullable=True))
    op.add_column("talk_submissions", sa.Column("start_time", sa.String(length=8), nullable=True))
    op.add_column("talk_submissions", sa.Column("end_time", sa.String(length=8), nullable=True))
    op.add_column("talk_submissions", sa.Column("capacity", sa.Integer(), nullable=True))


def downgrade():
    op.drop_column("talk_submissions", "capacity")
    op.drop_column("talk_submissions", "end_time")
    op.drop_column("talk_submissions", "start_time")
    op.drop_column("talk_submissions", "date")
