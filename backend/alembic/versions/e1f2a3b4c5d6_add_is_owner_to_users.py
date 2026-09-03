"""add is_owner to users

Revision ID: e1f2a3b4c5d6
Revises: d4e5f6a7b8c9
Create Date: 2026-06-27 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema

# revision identifiers
revision = 'e1f2a3b4c5d6'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.add_column('users', sa.Column(
        'is_owner',
        sa.Boolean(),
        server_default=sa.text('false'),
        nullable=False
    ))


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.drop_column('users', 'is_owner')
