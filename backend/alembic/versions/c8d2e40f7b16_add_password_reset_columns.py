"""add password reset columns to users

Revision ID: c8d2e40f7b16
Revises: a7f1c93d20b4
Create Date: 2026-08-28 00:00:01.000000

The reset code gets its own pair of columns rather than reusing
verification_code / verification_expiry. An account that never verified its
email can have a signup code and a reset code alive at the same time, and
sharing one column would have each flow silently expire the other's — the
member asks for a reset, and the signup code they were about to type stops
working.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d2e40f7b16'
down_revision: Union[str, Sequence[str], None] = 'a7f1c93d20b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('password_reset_code', sa.String(length=6), nullable=True))
    op.add_column('users', sa.Column('password_reset_expiry', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'password_reset_expiry')
    op.drop_column('users', 'password_reset_code')
