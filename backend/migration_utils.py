"""Helpers shared by the Alembic revisions.

Background — why any of this exists
-----------------------------------
For most of this project's life the schema was built by
``Base.metadata.create_all()`` at import time, not by Alembic. Alembic was only
reached for later ALTERs, and ``--autogenerate`` was usually run against a
database that ``create_all`` had *already* brought up to date, so six revisions
were generated completely empty and no revision ever created the 42 tables that
``create_all`` had made. The result: the history replayed fine on the
production database (which already had every table) and died immediately on an
empty one — ``relation "comment_reactions" does not exist``.

``ghawy_baseline`` is the fix. It is the new root of the history and it creates
the whole schema as production actually has it. Every revision that predates it
in *wall-clock* time still exists and still runs against the databases it was
written for; on a database built from the baseline there is by definition
nothing left for them to do, and they say so by calling
:func:`baseline_created_schema` and returning.

The marker table is what tells them apart. Only the baseline writes it, and it
only writes it when it genuinely created the schema itself.
"""

from alembic import op
import sqlalchemy as sa

MARKER_TABLE = "ghawy_schema_baseline"


def _bind():
    return op.get_bind()


def table_exists(name: str) -> bool:
    return sa.inspect(_bind()).has_table(name)


def baseline_created_schema() -> bool:
    """True when this database's schema came from the ``ghawy_baseline`` snapshot.

    A revision that predates the baseline should return immediately when this is
    true: the snapshot already contains its change. It is false for every
    database that existed before the baseline was written — production, and any
    dump taken from it — so those still replay the real history.
    """
    return table_exists(MARKER_TABLE)
