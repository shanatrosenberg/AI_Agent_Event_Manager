"""Add talk embedding vectors for semantic search

Revision ID: j8a2c01d3e56
Revises: i6e0a88b1f34
Create Date: 2026-10-06 14:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "j8a2c01d3e56"
down_revision = "i6e0a88b1f34"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "talk_embeddings",
        sa.Column("id", sa.String(length=96), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("document_text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("extra", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_talk_embeddings_source_type", "talk_embeddings", ["source_type"])
    op.create_index("ix_talk_embeddings_source_id", "talk_embeddings", ["source_id"])


def downgrade():
    op.drop_index("ix_talk_embeddings_source_id", table_name="talk_embeddings")
    op.drop_index("ix_talk_embeddings_source_type", table_name="talk_embeddings")
    op.drop_table("talk_embeddings")
