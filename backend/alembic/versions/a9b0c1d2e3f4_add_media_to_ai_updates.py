"""add media list to ai_update_posts + image_url to poll options

Revision ID: a9b0c1d2e3f4
Revises: f4a5b6c7d8e9
Create Date: 2026-07-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


revision: str = "a9b0c1d2e3f4"
down_revision: Union[str, Sequence[str], None] = "f4a5b6c7d8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.add_column("ai_update_posts", sa.Column("media", sa.JSON(), nullable=True))
    op.add_column("ai_update_poll_options", sa.Column("image_url", sa.String(), nullable=True))


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.drop_column("ai_update_poll_options", "image_url")
    op.drop_column("ai_update_posts", "media")
