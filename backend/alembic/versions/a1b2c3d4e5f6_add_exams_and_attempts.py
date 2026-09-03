"""add exams and exam attempts

Revision ID: a1b2c3d4e5f6
Revises: f3a4b5c6d7e8
Create Date: 2026-07-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "f3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("pass_percent", sa.Integer(), server_default=sa.text("70"), nullable=True),
        sa.Column("questions", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("is_published", sa.Boolean(), server_default=sa.text("false"), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exams_id"), "exams", ["id"], unique=False)
    op.create_index(op.f("ix_exams_course_id"), "exams", ["course_id"], unique=False)

    op.create_table(
        "exam_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exam_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("correct_count", sa.Integer(), nullable=False),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("answers", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exam_attempts_id"), "exam_attempts", ["id"], unique=False)
    op.create_index(op.f("ix_exam_attempts_exam_id"), "exam_attempts", ["exam_id"], unique=False)
    op.create_index(op.f("ix_exam_attempts_user_id"), "exam_attempts", ["user_id"], unique=False)


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.drop_index(op.f("ix_exam_attempts_user_id"), table_name="exam_attempts")
    op.drop_index(op.f("ix_exam_attempts_exam_id"), table_name="exam_attempts")
    op.drop_index(op.f("ix_exam_attempts_id"), table_name="exam_attempts")
    op.drop_table("exam_attempts")
    op.drop_index(op.f("ix_exams_course_id"), table_name="exams")
    op.drop_index(op.f("ix_exams_id"), table_name="exams")
    op.drop_table("exams")
