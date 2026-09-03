"""make chat reactions single per user

Revision ID: 4c8b2a19e7d4
Revises: 9b2d6f5a8c31
Create Date: 2026-06-09 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
from migration_utils import baseline_created_schema


revision: str = "4c8b2a19e7d4"
down_revision: Union[str, Sequence[str], None] = "9b2d6f5a8c31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.execute(
        """
        DELETE FROM chat_message_reactions a
        USING chat_message_reactions b
        WHERE a.message_id = b.message_id
          AND a.user_id = b.user_id
          AND a.id < b.id
        """
    )
    op.execute("ALTER TABLE chat_message_reactions DROP CONSTRAINT IF EXISTS uq_chat_message_reaction")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_chat_message_reaction_user'
            ) THEN
                ALTER TABLE chat_message_reactions
                ADD CONSTRAINT uq_chat_message_reaction_user UNIQUE (message_id, user_id);
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.execute("ALTER TABLE chat_message_reactions DROP CONSTRAINT IF EXISTS uq_chat_message_reaction_user")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_chat_message_reaction'
            ) THEN
                ALTER TABLE chat_message_reactions
                ADD CONSTRAINT uq_chat_message_reaction UNIQUE (message_id, user_id, emoji);
            END IF;
        END $$;
        """
    )
