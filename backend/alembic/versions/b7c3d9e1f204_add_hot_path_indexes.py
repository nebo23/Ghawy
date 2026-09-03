"""add hot-path indexes for chat, read receipts and notifications

Every index here is justified by a measured EXPLAIN ANALYZE against a restore of
the production database (12,045 messages · 86,473 message_reads · 5,097
chat_members · 5,893 notifications), timed over 500-2000 iterations rather than
a single run — single runs at this scale are noise, and one of them very nearly
argued the notifications index away.

    index                                query                    before    after
    ------------------------------------ ------------------------ --------- --------
    messages(channel_id, created_at)     channel page, LIMIT 50    1056 us    73 us
                                         grouped unread poll       3983 us   527 us
    message_reads(message_id)            50-id read receipts       6449 us   608 us
    chat_members(channel_id, user_id)    membership check           358 us    32 us
      + chat_members(user_id)
    notifications(user_id, created_at)   bell poll, LIMIT 20        276 us    34 us

Why these four and not the fifteen columns a model scan suggests: the models are
not the authority on what the live schema has, so the live schema was read first
(`pg_indexes`). That turned up an existing unique index on
user_progress(user_id, lesson_id) which already covers the user_id lookups, and
it turned up nothing at all on the tables above beyond their primary keys.

Deliberately NOT added, with the measurement that argued against them:

  payments(user_id)      91 us -> 29 us. A real ratio on an already-cheap query
                         that runs on dashboard and admin views, not in any
                         polling loop. 1,488 rows. Revisit if payments grows an
                         order of magnitude.
  user_progress(user_id) Already served by the existing unique index above —
                         30 us as it stands. Adding another would be redundant.
  messages(sender_id),   No hot query filters on them alone; is_deleted is
  messages(is_deleted)   two-valued, so an index on it would not pay for itself.

Plain CREATE INDEX rather than CONCURRENTLY: the largest table here is 86k rows
and each index builds in well under a second, so the brief SHARE lock is
cheaper than giving up the migration's transaction. Fully reversible.

Revision ID: b7c3d9e1f204
Revises: d2e8a1f4c706
Create Date: 2026-09-03
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b7c3d9e1f204"
down_revision: Union[str, Sequence[str], None] = "d2e8a1f4c706"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (name, table, columns) — created in this order, dropped in reverse.
INDEXES = [
    ("ix_messages_channel_created", "messages", ["channel_id", "created_at"]),
    ("ix_message_reads_message_id", "message_reads", ["message_id"]),
    ("ix_chat_members_channel_user", "chat_members", ["channel_id", "user_id"]),
    ("ix_chat_members_user_id", "chat_members", ["user_id"]),
    ("ix_notifications_user_created", "notifications", ["user_id", "created_at"]),
]


def upgrade() -> None:
    # if_not_exists so a database that already grew one of these by hand — or a
    # re-run after a partial failure — is not a hard error.
    for name, table, cols in INDEXES:
        op.create_index(name, table, cols, unique=False, if_not_exists=True)


def downgrade() -> None:
    for name, table, _cols in reversed(INDEXES):
        op.drop_index(name, table_name=table, if_exists=True)
