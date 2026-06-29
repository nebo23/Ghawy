"""add sort_order to courses

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-06-29 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('courses', sa.Column(
        'sort_order',
        sa.Integer(),
        server_default=sa.text('0'),
        nullable=False
    ))
    op.create_index('ix_courses_sort_order', 'courses', ['sort_order'])
    # Backfill existing rows with a stable initial order (matches id order)
    op.execute('UPDATE courses SET sort_order = id')


def downgrade() -> None:
    op.drop_index('ix_courses_sort_order', table_name='courses')
    op.drop_column('courses', 'sort_order')
