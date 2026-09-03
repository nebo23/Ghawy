"""add team_role to users

اسم الدور اللي الـ owner ركّبه على الأدمن (مدير مجتمع / مهندس تقني / نجاح
عملاء). تسمية بس — الصلاحيات الفعلية فاضلة في staff_permissions.

NULL = مفيش دور (عضو عادي، أو أدمن اتعمل قبل الفيتشر دي)، وده الديفولت
لكل الصفوف الموجودة: مفيش باك-فيل، لأن محدش يقدر يعرف الأدمن القديم كان
بيعمل إيه، وتخمين دور ليه هيوريه صلاحيات الـ owner ماداهاش له.

Revision ID: c9e1d3a7b542
Revises: b3d7e91c2a45
Create Date: 2026-09-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from migration_utils import baseline_created_schema


revision: str = 'c9e1d3a7b542'
down_revision: Union[str, Sequence[str], None] = 'b3d7e91c2a45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.add_column('users', sa.Column('team_role', sa.String(length=40), nullable=True))


def downgrade() -> None:
    # Predates ghawy_baseline: on a database built from that snapshot this
    # change is already present, so there is nothing to apply.
    if baseline_created_schema():
        return
    op.drop_column('users', 'team_role')
