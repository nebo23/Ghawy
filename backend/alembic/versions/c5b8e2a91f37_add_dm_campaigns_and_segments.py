"""announcements: delivery mode, send-as, failure reason, saved segments

Revision ID: c5b8e2a91f37
Revises: b7c3d9e1f204
Create Date: 2026-09-03

Four separate things, one migration, because they are one release and a
half-applied release is the worse outcome:

  announcements.delivery        'bell' | 'dm'. NOT NULL with a server default
                                of 'bell', which is what every existing row is:
                                a campaign written before this column existed
                                went to the notification bell, so the default
                                is not a guess, it is the fact. Adding the mode
                                must not change what any stored campaign does.

  announcements.sender_id       DM mode: whose account the member sees the
                                message from. Nullable — a bell campaign has no
                                "from". SET NULL on delete: the campaign record
                                outlives the account, and a deleted admin must
                                not take the history with them.

  announcements.sent_by         Who actually pushed the button. Separate from
                                sender_id on purpose; see the router docstring.
                                Also nullable and SET NULL, and NOT backfilled:
                                rows sent before this column existed genuinely
                                have no recorded actor, and writing created_by
                                into it would invent an audit trail rather than
                                record one.

  announcements.failure_reason  Why a campaign is sitting at 'failed'.

  messages.announcement_id      The DM path's delivery record, mirroring
                                notifications.announcement_id exactly — same
                                nullable FK, same ON DELETE SET NULL, same
                                index. Campaign stats and "who has already
                                received this" both read it, so it is indexed
                                for the same reason the notifications one is.

  announcement_segments         A named, reusable audience FILTER. Never a
                                resolved member list: the roster changes daily
                                and a frozen id list would quietly stop meaning
                                what its name says. Deleting a segment does not
                                touch campaigns built from it — each campaign
                                copies the filter into its own column when it
                                is saved.

Every column is nullable or carries a server default, so this applies to a
populated table without a rewrite and without a backfill step.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c5b8e2a91f37"
down_revision: Union[str, Sequence[str], None] = "b7c3d9e1f204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "announcements",
        sa.Column("delivery", sa.String(length=10), nullable=False,
                  server_default=sa.text("'bell'")),
    )
    op.add_column("announcements", sa.Column("sender_id", sa.Integer(), nullable=True))
    op.add_column("announcements", sa.Column("sent_by", sa.Integer(), nullable=True))
    op.add_column("announcements",
                  sa.Column("failure_reason", sa.String(length=300), nullable=True))
    op.create_foreign_key("fk_announcements_sender_id", "announcements", "users",
                          ["sender_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_announcements_sent_by", "announcements", "users",
                          ["sent_by"], ["id"], ondelete="SET NULL")

    op.add_column("messages", sa.Column("announcement_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_messages_announcement_id", "messages", "announcements",
                          ["announcement_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_messages_announcement_id", "messages", ["announcement_id"],
                    unique=False, if_not_exists=True)

    op.create_table(
        "announcement_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("filters", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("name", name="uq_announcement_segment_name"),
    )
    op.create_index("ix_announcement_segments_id", "announcement_segments", ["id"],
                    unique=False, if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_announcement_segments_id", table_name="announcement_segments",
                  if_exists=True)
    op.drop_table("announcement_segments")

    op.drop_index("ix_messages_announcement_id", table_name="messages", if_exists=True)
    op.drop_constraint("fk_messages_announcement_id", "messages", type_="foreignkey")
    op.drop_column("messages", "announcement_id")

    op.drop_constraint("fk_announcements_sent_by", "announcements", type_="foreignkey")
    op.drop_constraint("fk_announcements_sender_id", "announcements", type_="foreignkey")
    op.drop_column("announcements", "failure_reason")
    op.drop_column("announcements", "sent_by")
    op.drop_column("announcements", "sender_id")
    op.drop_column("announcements", "delivery")
