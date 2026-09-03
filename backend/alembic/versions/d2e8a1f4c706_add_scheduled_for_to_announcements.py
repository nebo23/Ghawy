"""add announcements.scheduled_for

Revision ID: d2e8a1f4c706
Revises: a1c4e77b9d20
Create Date: 2026-09-03

A campaign could only be sent by someone sitting at the tab at the moment it
should go out. This column is the whole of scheduling on the storage side: a
row with `status = 'scheduled'` and a due timestamp, which the scheduler picks
up on its next sweep.

Deliberately nullable with no default — an unscheduled campaign has no send
time, and NULL is that. Nothing needs backfilling: every existing row is a
draft or already sent.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd2e8a1f4c706'
down_revision: Union[str, Sequence[str], None] = 'a1c4e77b9d20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('announcements', sa.Column('scheduled_for', sa.DateTime(), nullable=True))
    # The scheduler sweeps "status = 'scheduled' AND scheduled_for <= now()"
    # every minute forever, so it gets an index rather than a repeated scan.
    op.create_index('ix_announcements_scheduled', 'announcements',
                    ['status', 'scheduled_for'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_announcements_scheduled', table_name='announcements')
    op.drop_column('announcements', 'scheduled_for')
