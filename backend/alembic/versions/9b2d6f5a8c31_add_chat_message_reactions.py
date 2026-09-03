"""add chat message reactions

Revision ID: 9b2d6f5a8c31
Revises: f1201efadb0f
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


revision: str = "9b2d6f5a8c31"
down_revision: Union[str, Sequence[str], None] = "f1201efadb0f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.create_table(
        "chat_message_reactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("emoji", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "user_id", name="uq_chat_message_reaction_user"),
    )
    op.create_index(op.f("ix_chat_message_reactions_id"), "chat_message_reactions", ["id"], unique=False)
    op.create_index(op.f("ix_chat_message_reactions_message_id"), "chat_message_reactions", ["message_id"], unique=False)
    op.create_index(op.f("ix_chat_message_reactions_user_id"), "chat_message_reactions", ["user_id"], unique=False)


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.drop_index(op.f("ix_chat_message_reactions_user_id"), table_name="chat_message_reactions")
    op.drop_index(op.f("ix_chat_message_reactions_message_id"), table_name="chat_message_reactions")
    op.drop_index(op.f("ix_chat_message_reactions_id"), table_name="chat_message_reactions")
    op.drop_table("chat_message_reactions")
