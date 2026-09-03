"""Query-count benchmark for the Phase 4 hot paths. Throwaway DB only.

Counts the SQL statements each endpoint issues, at production-shaped volumes, so
a change can be judged by measurement instead of by how the code reads.

    DATABASE_URL=postgresql://user:pw@host:5432/ghawy_test \
        python backend/scripts/bench_query_counts.py
"""
import os
os.environ.setdefault("SECRET_KEY", "dummy_secret_for_import_check")

from _acceptance_guard import require_scratch_database  # noqa: E402
require_scratch_database()

from datetime import datetime, timedelta            # noqa: E402
from fastapi.testclient import TestClient           # noqa: E402
from sqlalchemy import event, text as _text         # noqa: E402
import bcrypt                                       # noqa: E402

import main                                         # noqa: E402
from app.database import SessionLocal, engine       # noqa: E402
from app.models import Base                         # noqa: E402
from app import models as M                         # noqa: E402

# ── counter ────────────────────────────────────────────────────────────────
_stats = {"n": 0, "sql": []}


@event.listens_for(engine, "before_cursor_execute")
def _count(conn, cursor, statement, params, context, executemany):
    _stats["n"] += 1
    _stats["sql"].append(statement.split("\n")[0][:90])


class Count:
    def __init__(self, label):
        self.label = label

    def __enter__(self):
        _stats["n"] = 0
        _stats["sql"] = []
        return self

    def __exit__(self, *a):
        self.n = _stats["n"]
        self.sql = list(_stats["sql"])
        print(f"  {self.label:<46} {self.n:>4} queries")


with engine.begin() as c:
    c.execute(_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
engine.dispose()          # pooled connections still point at the dropped schema
Base.metadata.create_all(bind=engine)
with engine.connect() as c:
    n = c.execute(_text("SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema='public'")).scalar()
    print(f"schema rebuilt: {n} tables")
db = SessionLocal()

# ── fixtures at production shape: 4 group channels, 6 post slugs ───────────
def mkuser(email, **kw):
    u = M.User(email=email, hashed_password=bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode(),
               full_name=f"User {email}", is_active=True, is_verified=True, **kw)
    db.add(u); db.commit(); db.refresh(u)
    return u

me = mkuser("me@t.co")
senders = [mkuser(f"s{i}@t.co") for i in range(12)]

channels = []
for name in ("general", "help", "showcase", "random"):
    ch = M.Channel(name=name, channel_type=M.ChannelType.GROUP)
    db.add(ch); db.commit(); db.refresh(ch)
    channels.append(ch)
    db.add(M.ChatMember(channel_id=ch.id, user_id=me.id,
                        last_read_at=datetime.utcnow() - timedelta(days=1)))
    for s in senders:
        db.add(M.ChatMember(channel_id=ch.id, user_id=s.id))
db.commit()

main_ch = channels[0]
for i in range(300):
    db.add(M.Message(channel_id=main_ch.id, sender_id=senders[i % len(senders)].id,
                     content=f"message {i}",
                     created_at=datetime.utcnow() - timedelta(minutes=300 - i)))
for ch in channels[1:]:
    for i in range(40):
        db.add(M.Message(channel_id=ch.id, sender_id=senders[i % len(senders)].id,
                         content=f"m{i}"))
db.commit()

for slug in ("ideas", "wins", "questions", "jobs", "resources", "offtopic"):
    for i in range(8):
        db.add(M.Post(category_slug=slug, user_id=senders[i % len(senders)].id,
                      title=f"{slug} {i}", body="body text here"))
db.commit()

from app.routers.users import issue_token_for                      # noqa: E402
H = {"Authorization": "Bearer " + issue_token_for(me)}
client = TestClient(main.app, raise_server_exceptions=False)

print(f"\nfixtures: {len(channels)} group channels, 6 post slugs, "
      f"{db.query(M.Message).count()} messages, {db.query(M.Post).count()} posts\n")

print("P-2  GET /chat/channels/{id}/messages")
for limit in (20, 50):
    with Count(f"limit={limit}") as c:
        r = client.get(f"/chat/channels/{main_ch.id}/messages?limit={limit}", headers=H)
    assert r.status_code == 200, r.text
    got = len(r.json())
    print(f"       -> {got} messages returned, status {r.status_code}")

print("\nP-3  GET /chat/community/unread")
with Count("unread badge poll") as c3:
    r = client.get("/chat/community/unread", headers=H)
assert r.status_code == 200, r.text
print(f"       -> status {r.status_code}, body {str(r.json())[:110]}")

print("\nP-5  dashboard-adjacent endpoints")
for path in ("/dashboard/summary", "/chat/online-count", "/chat/channels"):
    with Count(path):
        client.get(path, headers=H)
