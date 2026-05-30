from app.database import SessionLocal
from app.models import User
from app.routers.users import create_token
from fastapi.testclient import TestClient
from main import app

db = SessionLocal()
admin_user = db.query(User).filter(User.is_admin == True).first()

if not admin_user:
    print("No admin user found")
    exit(1)

token = create_token(admin_user.id)
client = TestClient(app)

response = client.get("/courses/admin/4/lessons", headers={"Authorization": f"Bearer {token}"})
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
