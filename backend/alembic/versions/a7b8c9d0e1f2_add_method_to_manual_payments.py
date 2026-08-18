"""add method column to manual_payment_requests

Two manual rails now feed the same review queue — Instapay and Vodafone Cash —
and the reviewer cannot match a receipt without knowing which wallet the money
was sent to. Existing rows predate the second rail, so they are all Instapay:
the column is backfilled rather than left NULL, otherwise every historic
request would render as "unknown rail" in the team dashboard.

Revision ID: a7b8c9d0e1f2
Revises: b6c7d8e9f0a1
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'b6c7d8e9f0a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No DEFAULT on the ALTER: a plain nullable ADD COLUMN is a catalog-only
    # change and cannot rewrite the table (this DB has had ALTER TABLE hang on
    # a leaked idle-in-transaction before). The backfill is a separate UPDATE.
    op.execute("""
        ALTER TABLE manual_payment_requests
        ADD COLUMN IF NOT EXISTS method VARCHAR(20);
    """)
    op.execute("""
        UPDATE manual_payment_requests
        SET method = 'instapay'
        WHERE method IS NULL;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE manual_payment_requests DROP COLUMN IF EXISTS method;")
