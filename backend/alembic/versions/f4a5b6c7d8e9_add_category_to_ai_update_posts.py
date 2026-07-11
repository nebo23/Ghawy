"""add category to ai_update_posts

Revision ID: f4a5b6c7d8e9
Revises: e6f7a8b9c0d1
Create Date: 2026-07-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: Union[str, Sequence[str], None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("ai_update_posts") as batch_op:
        batch_op.add_column(
            sa.Column("category", sa.String(length=30), nullable=True)
        )
    # Backfill existing rows so the feed's default filter behaves predictably.
    op.execute("UPDATE ai_update_posts SET category = 'news' WHERE category IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("ai_update_posts") as batch_op:
        batch_op.drop_column("category")
