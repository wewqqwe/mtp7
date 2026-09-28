"""создать таблицы publishers и books

Revision ID: 0001
Revises:
Create Date: 2026-09-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publishers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("city", sa.String(100), nullable=False),
    )
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column(
            "publisher_id",
            sa.Integer(),
            sa.ForeignKey("publishers.id"),
            nullable=True,
        ),
        sa.CheckConstraint("year BETWEEN 1800 AND 2100", name="ck_books_year"),
    )


def downgrade() -> None:
    op.drop_table("books")
    op.drop_table("publishers")
