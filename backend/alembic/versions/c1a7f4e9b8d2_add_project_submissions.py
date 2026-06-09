"""add project submissions

Revision ID: c1a7f4e9b8d2
Revises: 4c8b2a19e7d4
Create Date: 2026-06-09 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1a7f4e9b8d2"
down_revision: Union[str, Sequence[str], None] = "4c8b2a19e7d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_submissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("file_url", sa.String(), nullable=False),
        sa.Column("json_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_submissions_id"), "project_submissions", ["id"], unique=False)
    op.create_index(op.f("ix_project_submissions_user_id"), "project_submissions", ["user_id"], unique=False)
    op.create_index(op.f("ix_project_submissions_course_id"), "project_submissions", ["course_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_project_submissions_course_id"), table_name="project_submissions")
    op.drop_index(op.f("ix_project_submissions_user_id"), table_name="project_submissions")
    op.drop_index(op.f("ix_project_submissions_id"), table_name="project_submissions")
    op.drop_table("project_submissions")
