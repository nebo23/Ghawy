"""add certificate_url to courses

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-07-08 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7a8b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.add_column("courses", sa.Column("certificate_url", sa.String(), nullable=True))


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.drop_column("courses", "certificate_url")
