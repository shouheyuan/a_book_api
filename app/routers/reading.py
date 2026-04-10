import uuid, json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, Any
from app.db import get_db
from app.core.auth import get_current_user_id

router = APIRouter()

class ReadingSessionSync(BaseModel):
    book_identifier: str
    book_title: Optional[str] = None
    cover_path: Optional[str] = None
    locator_json: Optional[Any] = None
    progression: Optional[float] = None

@router.post("")
def sync_reading(body: ReadingSessionSync, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    existing = db.execute(text(
        "SELECT id FROM reading_sessions WHERE user_id = :uid AND book_identifier = :bid"
    ), {"uid": user_id, "bid": body.book_identifier}).fetchone()

    locator = json.dumps(body.locator_json) if body.locator_json is not None else None

    if existing:
        db.execute(text(
            "UPDATE reading_sessions SET locator_json = :loc, progression = :prog, "
            "book_title = :title, cover_path = :cover, last_read_at = NOW(), updated_at = NOW() WHERE id = :id"
        ), {"loc": locator, "prog": body.progression, "title": body.book_title, "cover": body.cover_path, "id": existing.id})
    else:
        db.execute(text(
            "INSERT INTO reading_sessions (id, user_id, book_identifier, book_title, cover_path, locator_json, progression, last_read_at) "
            "VALUES (:id, :uid, :bid, :title, :cover, :loc, :prog, NOW())"
        ), {"id": str(uuid.uuid4()), "uid": user_id, "bid": body.book_identifier,
            "title": body.book_title, "cover": body.cover_path, "loc": locator, "prog": body.progression})
    db.commit()
    return {"message": "synced"}

@router.get("")
def get_reading_sessions(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT * FROM reading_sessions WHERE user_id = :uid ORDER BY last_read_at DESC"
    ), {"uid": user_id}).fetchall()
    result = []
    for r in rows:
        d = dict(r._mapping)
        if d.get("locator_json") and isinstance(d["locator_json"], str):
            try:
                d["locator_json"] = json.loads(d["locator_json"])
            except Exception:
                pass
        if d.get("last_read_at"):
            d["last_read_at"] = d["last_read_at"].isoformat()
        if d.get("updated_at"):
            d["updated_at"] = d["updated_at"].isoformat()
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        result.append(d)
    return result

@router.delete("/{book_identifier}")
def delete_reading_session(book_identifier: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    db.execute(text(
        "DELETE FROM reading_sessions WHERE user_id = :uid AND book_identifier = :bid"
    ), {"uid": user_id, "bid": book_identifier})
    db.commit()
    return {"message": "deleted"}
