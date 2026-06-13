"""merge multiple heads

Revision ID: 4823c6c0b288
Revises: 307efdf1db45, c1a7f4e9b8d2
Create Date: 2026-06-12 01:22:38.603701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4823c6c0b288'
down_revision: Union[str, Sequence[str], None] = ('307efdf1db45', 'c1a7f4e9b8d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
