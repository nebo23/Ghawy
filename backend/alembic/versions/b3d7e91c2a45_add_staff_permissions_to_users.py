"""add staff_permissions to users

صلاحيات الأدمن اللي الـ owner بيفتحها من لوحة الفريق. NULL = الديفولت القديم.

Revision ID: b3d7e91c2a45
Revises: c8d2e40f7b16
Create Date: 2026-09-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3d7e91c2a45'
down_revision: Union[str, Sequence[str], None] = 'c8d2e40f7b16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('staff_permissions', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'staff_permissions')
