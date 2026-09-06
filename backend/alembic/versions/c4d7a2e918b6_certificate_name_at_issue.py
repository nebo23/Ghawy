"""certificates: the name the certificate was issued under

Revision ID: c4d7a2e918b6
Revises: b3c9e1f47a25
Create Date: 2026-09-06

The certificate PNG is drawn in the browser at download time from the member's
live `full_name`, and the row stored no name at all. So a member who renames
themselves downloads a second certificate bearing a different name under the
same verification ID, and the copy already on their laptop no longer matches
anything. `PUT /profile/me` has always allowed a rename, and the Arabic-name
ratchet still permits Latin→Latin edits, so this is reachable today — it is not
something the onboarding name step introduced (that runs after payment and
before any course is finished).

Backfilled from each member's current `full_name`, which is the honest value:
it is exactly what those certificates render today. Rows are only ever written
here at issue time afterwards.

Nullable on purpose. A null means "no snapshot was taken", and the download
falls back to the live name — the behaviour every certificate had before this.
"""
from alembic import op
import sqlalchemy as sa


revision = 'c4d7a2e918b6'
down_revision = 'b3c9e1f47a25'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('certificates', sa.Column('full_name_at_issue', sa.String(), nullable=True))
    # The best value available for a row issued before the column existed.
    op.execute("""
        UPDATE certificates c
           SET full_name_at_issue = u.full_name
          FROM users u
         WHERE u.id = c.user_id
           AND c.full_name_at_issue IS NULL
    """)


def downgrade():
    op.drop_column('certificates', 'full_name_at_issue')
