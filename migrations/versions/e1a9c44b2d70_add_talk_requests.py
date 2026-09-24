"""Add talk requests and submission organizer_id

Revision ID: e1a9c44b2d70
Revises: d8e3b12c9a44
Create Date: 2026-09-24 13:55:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e1a9c44b2d70"
down_revision = "d8e3b12c9a44"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("talk_submissions", sa.Column("organizer_id", sa.String(length=64), nullable=True))
    op.create_table(
        "talk_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organizer_id", sa.String(length=64), nullable=False),
        sa.Column("speaker_id", sa.String(length=64), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("submission_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["organizer_id"], ["organizers.id"]),
        sa.ForeignKeyConstraint(["speaker_id"], ["speakers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("talk_requests")
    op.drop_column("talk_submissions", "organizer_id")
