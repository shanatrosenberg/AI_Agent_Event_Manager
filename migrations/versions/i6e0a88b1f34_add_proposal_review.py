"""Add proposal review, trash, and event link columns

Revision ID: i6e0a88b1f34
Revises: h5d9f77a0e23
Create Date: 2026-09-24 15:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "i6e0a88b1f34"
down_revision = "h5d9f77a0e23"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("talk_submissions", sa.Column("event_id", sa.String(length=36), nullable=True))
    op.add_column("talk_submissions", sa.Column("rejected_at", sa.DateTime(), nullable=True))
    op.add_column("talk_submissions", sa.Column("rejection_message", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("talk_submissions", "rejection_message")
    op.drop_column("talk_submissions", "rejected_at")
    op.drop_column("talk_submissions", "event_id")
