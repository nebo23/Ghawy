"""add vdo_video_id to lessons

Revision ID: b7c9d1e2f3a4
Revises: ec6b20b59525
Create Date: 2026-06-24 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


# revision identifiers, used by Alembic.
revision: str = 'b7c9d1e2f3a4'
down_revision: Union[str, Sequence[str], None] = '37f54e72ee27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    # Use raw SQL to safely add column (avoids error if already exists from manual SQL)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE lessons ADD COLUMN vdo_video_id VARCHAR;
        EXCEPTION
            WHEN duplicate_column THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.drop_column('lessons', 'vdo_video_id')
