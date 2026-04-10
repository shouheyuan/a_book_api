from app.db import SessionLocal
from sqlalchemy import text
import uuid
import json

db = SessionLocal()
try:
    rec_id = str(uuid.uuid4())
    # Instead of foreign key constraint failure, let's insert a valid user_id
    user_id = db.execute(text("SELECT id FROM user_profiles LIMIT 1")).scalar()
    if user_id:
        db.execute(text(
            "INSERT INTO ai_images (id, user_id, book_id, paragraph_id, prompt, image_urls) "
            "VALUES (:id, :uid, :bid, :pid, :prompt, :urls)"
        ), {"id": rec_id, "uid": user_id, "bid": "test_book", "pid": "test_pid",
            "prompt": "test_prompt", "urls": json.dumps(["http://example.com/test.jpg"])})
        db.commit()
    
    rows = db.execute(text("SELECT * FROM ai_images")).fetchall()
    print([dict(r._mapping) for r in rows])
finally:
    db.close()
