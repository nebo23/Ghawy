"""add announcements table and notifications.announcement_id

Revision ID: a1c4e77b9d20
Revises: c9e1d3a7b542
Create Date: 2026-09-03 00:00:00.000000

Chains onto c9e1d3a7b542 (add team_role to users), the head after the Phase 1
migration rebuild landed. The tree now has one root (ghawy_baseline) and one
head, and this extends it — no merge revision involved.

In-app announcements (member campaigns), the counterpart to the email
campaigns tab. Delivery reuses the existing `notifications` table: each
recipient gets an ordinary notification row tagged with `announcement_id`,
which is also what makes delivered/read stats possible without a second
table.

`ondelete="SET NULL"` on the FK is deliberate: deleting a campaign row must
never delete notifications that already reached members. They keep what they
were sent; only the campaign's own record goes.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'a1c4e77b9d20'
down_revision = 'c9e1d3a7b542'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('type', sa.String(length=20), server_default=sa.text("'info'"), nullable=False),
        sa.Column('link', sa.String(), nullable=True),
        sa.Column('audience', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default=sa.text("'draft'"), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('recipients_count', sa.Integer(), server_default=sa.text('0'), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_announcements_id', 'announcements', ['id'])

    op.add_column('notifications', sa.Column('announcement_id', sa.Integer(), nullable=True))
    op.create_index('ix_notifications_announcement_id', 'notifications', ['announcement_id'])
    op.create_foreign_key(
        'fk_notifications_announcement_id', 'notifications', 'announcements',
        ['announcement_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_notifications_announcement_id', 'notifications', type_='foreignkey')
    op.drop_index('ix_notifications_announcement_id', table_name='notifications')
    op.drop_column('notifications', 'announcement_id')

    op.drop_index('ix_announcements_id', table_name='announcements')
    op.drop_table('announcements')
