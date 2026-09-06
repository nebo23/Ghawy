"""users: the member said their name is not written in Arabic

Revision ID: b3c9e1f47a25
Revises: a7c2f1d38b40
Create Date: 2026-09-06

New members are asked to write their name in Arabic — in the signup form, and
in onboarding for a Google signup once they have paid. The ask cannot be a
lock: a member whose name simply is not written in Arabic cannot comply, and
the roster already has a few. This flag is their way out. They tick «اسمي مش
بالعربي», the Latin name is stored as typed, and nothing asks again.

Not a migration of anything. Every existing row gets `false`, which is exactly
right: the 1,683 Latin names on the roster today are outside this rule and are
never asked. `false` here means "has not opted out", not "must be Arabic" —
the rule only ever runs at a door a new name comes through.

NOT NULL with a server default, so the column is answerable for every row from
the moment it exists and no read has to treat NULL as a third state.
"""
from alembic import op
import sqlalchemy as sa


revision = 'b3c9e1f47a25'
down_revision = 'a7c2f1d38b40'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('latin_name_ok', sa.Boolean(),
                                     nullable=False, server_default=sa.text('false')))


def downgrade():
    op.drop_column('users', 'latin_name_ok')
