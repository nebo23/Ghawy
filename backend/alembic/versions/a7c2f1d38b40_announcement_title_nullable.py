"""announcements: the title is optional — a campaign is one piece of text

Revision ID: a7c2f1d38b40
Revises: d1e4f7a2b9c3
Create Date: 2026-09-05

The composer asked for a title and a body and refused to send without both.
In DM mode the title was never a title: `_dm_body` glued it on as the first
line of the message, because a chat bubble has nowhere else to put it. In bell
mode it was a real heading, and operators were writing the same sentence twice
— once short for the heading, once properly in the body.

So the field is gone from the composer and the column follows it to nullable.
Dropping the column instead would erase the headings of every campaign already
sent, which the history view still shows; and the bell's own `title` column
stays NOT NULL, because that is a platform-wide contract that every other
notification on the site depends on. A title-less campaign writes "" into it
and the bell renderer promotes the body into the heading slot.

Nothing to backfill: existing rows all have titles and keep them.

Reversible: the down path fills any NULL with the body's first line before
restoring NOT NULL, so a downgrade cannot fail on rows written after this.
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7c2f1d38b40'
down_revision = 'd1e4f7a2b9c3'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('announcements', 'title',
                    existing_type=sa.String(length=160),
                    nullable=True)


def downgrade():
    op.execute("""
        UPDATE announcements
           SET title = LEFT(SPLIT_PART(COALESCE(body, ''), E'\\n', 1), 160)
         WHERE title IS NULL
    """)
    op.execute("UPDATE announcements SET title = '(بدون عنوان)' WHERE COALESCE(title, '') = ''")
    op.alter_column('announcements', 'title',
                    existing_type=sa.String(length=160),
                    nullable=False)
