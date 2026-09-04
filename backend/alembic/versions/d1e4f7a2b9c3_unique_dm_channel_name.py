"""channels: one DM channel per pair, enforced by the schema (F-30)

Revision ID: d1e4f7a2b9c3
Revises: c5b8e2a91f37
Create Date: 2026-09-04

Until now the guarantee that two people have exactly one conversation rested
entirely on application code: a deterministic name `dm_{low}_{high}` and a
`SELECT ... .first()`. Nothing in the schema said so.

That was theoretical while the only way to create a DM was one person opening
one conversation. It stopped being theoretical when DM campaigns landed. The
fan-out does check-then-create for every pair; `get_or_create_dm_channel` does
check-then-create for a single pair. `_send_lock` serialises fan-outs against
each other — it cannot serialise a fan-out against a member who opens a DM with
the sender while it is running, because that is a member action behind no lock.
Two rows named `dm_5_129` is the outcome, and the symptom is not an error: it
is a member with their conversation permanently split across two threads,
noticed only when they ask why.

WHAT THIS DOES

  1. Counts duplicates and merges them, keeping the LOWEST id. That is not an
     arbitrary choice — `find_dm_channel` uses `.first()` and `ensure_dm_channels`
     orders by `id ASC`, so the lowest id is already the row both code paths
     resolve to. Merging into it means the surviving channel is the one the
     application was going to pick anyway, and the merge cannot change which
     thread a member sees.

     Messages and memberships move to the survivor; memberships that would
     collide are dropped rather than duplicated. Then the surplus rows go.

  2. Adds `uq_channels_dm_name` — UNIQUE (name) WHERE channel_type = 'DM'.

     Partial on purpose. Group channels are a different question with different
     rules (four of them exist, and "two groups may not share a name" is a
     product decision nobody has made); this constraint is about the DM naming
     scheme specifically, which is machine-generated and genuinely must be
     unique.

     From here a concurrent double-create is an IntegrityError — a loud,
     catchable event at the moment it happens — instead of a second channel
     that nobody sees until a member complains.

ON PRODUCTION AS OF 2026-09-04

  1,486 DM channels, 4 group channels, ZERO duplicate names of any kind, and
  zero DM names that fail the `dm_<int>_<int>` shape. The merge step is
  therefore a no-op here. It is written anyway because this migration also runs
  against restores, scratch databases and any future clone, and a constraint
  that fails on real data at 3am is worse than a merge step that does nothing.

  (The same sweep did find 6 DM channels with no members and 23 with exactly
  one. Those are NOT duplicates and this migration deliberately leaves them
  alone — deleting rows is not a schema change. See F-35.)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e4f7a2b9c3"
down_revision: Union[str, Sequence[str], None] = "c5b8e2a91f37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "uq_channels_dm_name"


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. how bad is it, actually ────────────────────────────────────────
    dupes = conn.execute(sa.text("""
        SELECT name, count(*) AS n
        FROM channels
        WHERE channel_type = 'DM'
        GROUP BY name
        HAVING count(*) > 1
        ORDER BY n DESC
    """)).fetchall()

    if dupes:
        surplus = sum(int(r.n) - 1 for r in dupes)
        print(f"[{revision}] {len(dupes)} duplicated DM channel name(s), "
              f"{surplus} surplus row(s) — merging into the lowest id of each")

        # Messages move first. `messages.channel_id` has no uniqueness of its
        # own, so this is a plain re-point; ordering within the merged thread
        # stays correct because the reader sorts by created_at, not by id.
        conn.execute(sa.text("""
            WITH keep AS (
                SELECT name, min(id) AS survivor
                FROM channels WHERE channel_type = 'DM'
                GROUP BY name HAVING count(*) > 1
            ),
            doomed AS (
                SELECT c.id, k.survivor
                FROM channels c JOIN keep k ON k.name = c.name
                WHERE c.channel_type = 'DM' AND c.id <> k.survivor
            )
            UPDATE messages m SET channel_id = d.survivor
            FROM doomed d WHERE m.channel_id = d.id
        """))

        # Memberships next, skipping any the survivor already has — the common
        # case, since both rows describe the same pair of people.
        conn.execute(sa.text("""
            WITH keep AS (
                SELECT name, min(id) AS survivor
                FROM channels WHERE channel_type = 'DM'
                GROUP BY name HAVING count(*) > 1
            ),
            doomed AS (
                SELECT c.id, k.survivor
                FROM channels c JOIN keep k ON k.name = c.name
                WHERE c.channel_type = 'DM' AND c.id <> k.survivor
            )
            UPDATE chat_members cm SET channel_id = d.survivor
            FROM doomed d
            WHERE cm.channel_id = d.id
              AND NOT EXISTS (
                  SELECT 1 FROM chat_members x
                  WHERE x.channel_id = d.survivor AND x.user_id = cm.user_id
              )
        """))

        # Whatever is left on a doomed channel is a duplicate membership row;
        # the CASCADE below removes it with the channel.
        deleted = conn.execute(sa.text("""
            WITH keep AS (
                SELECT name, min(id) AS survivor
                FROM channels WHERE channel_type = 'DM'
                GROUP BY name HAVING count(*) > 1
            )
            DELETE FROM channels c
            USING keep k
            WHERE c.channel_type = 'DM' AND c.name = k.name AND c.id <> k.survivor
            RETURNING c.id
        """)).fetchall()
        print(f"[{revision}] merged and removed {len(deleted)} duplicate channel row(s)")
    else:
        print(f"[{revision}] no duplicate DM channel names — nothing to merge")

    # ── 2. make it structural ─────────────────────────────────────────────
    op.create_index(
        INDEX_NAME,
        "channels",
        ["name"],
        unique=True,
        postgresql_where=sa.text("channel_type = 'DM'"),
    )


def downgrade() -> None:
    # Only the index comes back off. The merge is not reversible and must not
    # pretend to be: the duplicate rows are gone and re-splitting a conversation
    # that has been whole since the upgrade would be inventing data.
    op.drop_index(INDEX_NAME, table_name="channels")
