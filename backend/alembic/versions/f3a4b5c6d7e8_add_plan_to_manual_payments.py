"""add plan column to manual_payment_requests

Revision ID: f3a4b5c6d7e8
Revises: b7c8d9e0f1a2
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, Sequence[str], None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    # Add plan column (safe: no-op if already present, no default => fast catalog change)
    op.execute("""
        ALTER TABLE manual_payment_requests
        ADD COLUMN IF NOT EXISTS plan VARCHAR;
    """)


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.execute("ALTER TABLE manual_payment_requests DROP COLUMN IF EXISTS plan;")
