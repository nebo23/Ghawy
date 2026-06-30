"""add person_user_id and image_url to feedbacks, make person_email nullable

Revision ID: b7c8d9e0f1a2
Revises: f2a3b4c5d6e7
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New feedbacks identify the member by id and may carry an image.
    # Plain integer (no FK) to avoid taking a lock on the busy users table.
    op.execute("""
        ALTER TABLE feedbacks
        ADD COLUMN IF NOT EXISTS person_user_id INTEGER;
    """)
    op.execute("""
        ALTER TABLE feedbacks
        ADD COLUMN IF NOT EXISTS image_url VARCHAR;
    """)
    # person_email is legacy now — keep existing values but stop requiring it.
    op.execute("ALTER TABLE feedbacks ALTER COLUMN person_email DROP NOT NULL;")


def downgrade() -> None:
    op.execute("ALTER TABLE feedbacks DROP COLUMN IF EXISTS person_user_id;")
    op.execute("ALTER TABLE feedbacks DROP COLUMN IF EXISTS image_url;")
    # Note: not restoring NOT NULL on person_email to avoid failing on null rows.
