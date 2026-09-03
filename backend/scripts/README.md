# backend/scripts

Destructive acceptance scripts. **These are not tests** — they are standalone
programs that rebuild the schema from the models and then drive the real app
through `TestClient`.

They used to live in `backend/tests/` under `test_*.py` names, which meant a
bare `pytest` would import them and, at import time, run

```sql
DROP SCHEMA public CASCADE; CREATE SCHEMA public;
```

against whatever `DATABASE_URL` happened to be in the environment. They were
moved here and renamed so that can no longer happen by accident.

## Running one

Every script calls `require_scratch_database()` (see `_acceptance_guard.py`)
before it imports the application, and refuses to start unless the target
database is *named* as a throwaway — `ghawy_test`, `scratch_db`, `tmp_db` and
so on. It prints the database it is about to destroy before destroying it.

```bash
DATABASE_URL=postgresql://user:pass@host:5432/ghawy_test \
    python backend/scripts/acceptance_security.py
```

The check is on the database **name**, not the host: on this deployment the
production database is published on `127.0.0.1:5432` and answers to the host
`postgres` inside the compose network, so "localhost" proves nothing. The name
configured for production is refused outright, including via the override.

To target a database whose name does not look disposable, name it explicitly:

```bash
ACCEPTANCE_DESTROY_DB=my_db DATABASE_URL=postgresql://.../my_db python ...
```

## The scripts

| Script | Covers |
| --- | --- |
| `acceptance_security.py` | Access control across courses, lessons, files, chat, admin |
| `acceptance_atlas_promo_and_reset.py` | Atlas free-month promo rounds, password reset |
| `acceptance_team_roles.py` | Named team roles and the permissions they grant |

Real tests — ones safe to run anywhere — belong in `backend/tests/`.
