"""Add password_hash to role accounts

Revision ID: c4f2a91e7b10
Revises: 49b8b8580d18
Create Date: 2026-09-24 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c4f2a91e7b10"
down_revision = "49b8b8580d18"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("organizers", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("speakers", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("attendees", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column("attendees", "password_hash")
    op.drop_column("speakers", "password_hash")
    op.drop_column("organizers", "password_hash")
