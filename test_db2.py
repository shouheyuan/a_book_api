from app.db import SessionLocal
from sqlalchemy import text
from fastapi.encoders import jsonable_encoder

db = SessionLocal()
try:
    user_id = db.execute(text("SELECT id FROM user_profiles LIMIT 1")).scalar()
    rows = db.execute(text(
        "SELECT * FROM ai_images WHERE user_id = :uid ORDER BY created_at DESC"
    ), {"uid": user_id}).fetchall()
    res = [dict(r._mapping) for r in rows]
    print(res)
finally:
    db.close()
