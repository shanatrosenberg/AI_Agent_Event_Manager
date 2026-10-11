"""Add selected hall seat labels on bookings

Revision ID: l0c4e23f5g78
Revises: k9b3d12e4f67
Create Date: 2026-10-11 22:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "l0c4e23f5g78"
down_revision = "k9b3d12e4f67"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.add_column(sa.Column("seat_labels", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("bookings") as batch_op:
        batch_op.drop_column("seat_labels")
