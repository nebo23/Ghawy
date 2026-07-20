"""add automated email flags (first lesson, course completion, 5-day expiry)

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-20 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("first_lesson_email_sent_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("expiry5_email_sent_for", sa.DateTime(), nullable=True))
    op.add_column("certificates", sa.Column("completion_email_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("certificates", "completion_email_sent_at")
    op.drop_column("users", "expiry5_email_sent_for")
    op.drop_column("users", "first_lesson_email_sent_at")
