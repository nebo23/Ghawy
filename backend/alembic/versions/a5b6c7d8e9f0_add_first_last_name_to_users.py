"""add first_name / last_name to users

The signup form now collects the name in two fields. `full_name` stays as the
display source of truth (read in 20+ places: emails, chat, DMs, admin, the team
dashboard) and is recomposed from first + last, so nothing downstream changes.

Existing rows are backfilled by splitting full_name on the first space:
    "محمد أحمد علي" -> first="محمد", last="أحمد علي"
    "Mohamed"        -> first="Mohamed", last=""

Revision ID: a5b6c7d8e9f0
Revises: e4f5a6b7c8d9
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


revision: str = "a5b6c7d8e9f0"
down_revision: Union[str, Sequence[str], None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.add_column("users", sa.Column("first_name", sa.String(), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(), nullable=True))

    # Backfill from the existing display name. split_part(x, ' ', 1) is the part
    # before the first space; substring(... from position(' ' in ...) + 1) is
    # everything after it. Names without a space get last_name = ''.
    op.execute(
        """
        UPDATE users
        SET first_name = split_part(btrim(full_name), ' ', 1),
            last_name = CASE
                WHEN position(' ' in btrim(full_name)) = 0 THEN ''
                ELSE btrim(substring(btrim(full_name)
                                     from position(' ' in btrim(full_name)) + 1))
            END
        WHERE full_name IS NOT NULL
        """
    )


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.drop_column("users", "last_name")
    op.drop_column("users", "first_name")
