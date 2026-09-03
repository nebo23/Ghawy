"""add after_lesson_id to exams for curriculum placement

Revision ID: c4d5e6f7a8b9
Revises: b8c9d0e1f2a3
Create Date: 2026-07-08 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.add_column("exams", sa.Column("after_lesson_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_exams_after_lesson_id"), "exams", ["after_lesson_id"], unique=False)
    op.create_foreign_key(
        "fk_exams_after_lesson_id_lessons",
        "exams",
        "lessons",
        ["after_lesson_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.drop_constraint("fk_exams_after_lesson_id_lessons", "exams", type_="foreignkey")
    op.drop_index(op.f("ix_exams_after_lesson_id"), table_name="exams")
    op.drop_column("exams", "after_lesson_id")
