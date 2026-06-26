"""add admin_member_notes table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create admin_member_notes table (safe: no-op if already present)
    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_member_notes (
            id SERIAL PRIMARY KEY,
            member_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            note TEXT NOT NULL DEFAULT '',
            updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT now(),
            updated_at TIMESTAMP DEFAULT now()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_admin_member_notes_member_id
        ON admin_member_notes (member_id);
    """)


def downgrade() -> None:
    op.drop_table('admin_member_notes')
