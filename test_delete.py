from sqlalchemy import create_engine
engine = create_engine("postgresql://ghawy_user:Ghawy_DB_Pass_2026!@localhost:5432/ghawy_db")
with engine.connect() as con:
    rs = con.execute("SELECT id FROM users LIMIT 1")
    print(rs.fetchone())
