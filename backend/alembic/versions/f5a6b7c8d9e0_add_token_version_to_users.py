"""add token_version to users (JWT revocation)

Revision ID: f5a6b7c8d9e0
Revises: a7b8c9d0e1f2
Create Date: 2026-08-21

Sessions are 30-day JWTs with no server-side state, so logging out only cleared
localStorage and a stolen token stayed good for a month. This column is the
revocation point: the value is stamped into every token at issue time and
compared on every request, so bumping it invalidates that user's tokens at once.

Adding an integer column WITH a default is metadata-only on PostgreSQL 11+ — no
table rewrite — but it still takes a brief ACCESS EXCLUSIVE lock on `users`, the
busiest table here. lock_timeout makes that fail fast instead of queueing behind
a long-running transaction while every other query piles up behind it. If it
does time out, find the blocker in pg_stat_activity (usually a leaked
idle-in-transaction session), terminate it, and re-run.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


# revision identifiers, used by Alembic.
revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.execute("SET lock_timeout = '5s'")
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.execute("SET lock_timeout = DEFAULT")


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.execute("SET lock_timeout = '5s'")
    op.drop_column("users", "token_version")
    op.execute("SET lock_timeout = DEFAULT")
