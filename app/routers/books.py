import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.db import get_db
from app.core.auth import get_current_user_id

router = APIRouter()

class AddToShelfRequest(BaseModel):
    book_id: str
    is_downloaded: Optional[bool] = False
    local_path: Optional[str] = None

@router.get("/books")
def search_books(q: Optional[str] = Query(None), limit: int = Query(20), offset: int = Query(0), db: Session = Depends(get_db)):
    if q:
        rows = db.execute(text(
            "SELECT * FROM books WHERE title LIKE :q OR author LIKE :q LIMIT :limit OFFSET :offset"
        ), {"q": f"%{q}%", "limit": limit, "offset": offset}).fetchall()
    else:
        rows = db.execute(text("SELECT * FROM books LIMIT :limit OFFSET :offset"), {"limit": limit, "offset": offset}).fetchall()
    return [dict(r._mapping) for r in rows]

@router.post("/books/shelf")
def add_to_shelf(body: AddToShelfRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    existing = db.execute(text(
        "SELECT id FROM user_books WHERE user_id = :uid AND book_id = :bid"
    ), {"uid": user_id, "bid": body.book_id}).fetchone()
    if existing:
        return {"message": "already in shelf", "id": existing.id}
    shelf_id = str(uuid.uuid4())
    db.execute(text(
        "INSERT INTO user_books (id, user_id, book_id, is_downloaded, local_path) VALUES (:id, :uid, :bid, :dl, :path)"
    ), {"id": shelf_id, "uid": user_id, "bid": body.book_id, "dl": body.is_downloaded, "path": body.local_path})
    db.commit()
    return {"message": "added", "id": shelf_id}

@router.get("/books/shelf")
def get_shelf(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.execute(text("""
        SELECT ub.id, ub.book_id, ub.is_downloaded, ub.local_path, ub.added_at,
               b.title, b.author, b.cover_url, b.file_url, b.is_free, b.coin_price
        FROM user_books ub
        LEFT JOIN books b ON ub.book_id = b.id
        WHERE ub.user_id = :uid
        ORDER BY ub.added_at DESC
    """), {"uid": user_id}).fetchall()
    return [dict(r._mapping) for r in rows]

@router.delete("/books/shelf/{user_book_id}")
def remove_from_shelf(user_book_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM user_books WHERE id = :id AND user_id = :uid"), {"id": user_book_id, "uid": user_id})
    db.commit()
    return {"message": "removed"}
