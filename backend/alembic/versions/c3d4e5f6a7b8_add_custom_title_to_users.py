"""add custom_title to users

Revision ID: c3d4e5f6a7b8
Revises: b7c9d1e2f3a4
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b7c9d1e2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add custom_title column (safe: no-op if already present)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN custom_title VARCHAR(120);
        EXCEPTION
            WHEN duplicate_column THEN NULL;
        END $$;
    """)

    # Seed custom titles for the two specific accounts
    op.execute("""
        UPDATE users SET custom_title = 'Community Manager'
        WHERE email = 'moatazahmed737@gmail.com';
    """)
    op.execute("""
        UPDATE users SET custom_title = 'Technical Engineer'
        WHERE email = 'abdosalama2809@gmail.com';
    """)


def downgrade() -> None:
    op.drop_column('users', 'custom_title')
