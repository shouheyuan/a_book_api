import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.db import get_db
from app.core.auth import get_current_user_id

router = APIRouter()

class CollectionCreate(BaseModel):
    name: str
    sort_order: Optional[int] = 0

class AddBookToCollection(BaseModel):
    user_book_id: str

@router.post("")
def create_collection(body: CollectionCreate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    col_id = str(uuid.uuid4())
    db.execute(text(
        "INSERT INTO collections (id, user_id, name, sort_order) VALUES (:id, :uid, :name, :sort)"
    ), {"id": col_id, "uid": user_id, "name": body.name, "sort": body.sort_order})
    db.commit()
    return {"id": col_id, "message": "created"}

@router.get("")
def get_collections(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT * FROM collections WHERE user_id = :uid ORDER BY sort_order ASC, created_at DESC"
    ), {"uid": user_id}).fetchall()
    return [dict(r._mapping) for r in rows]

@router.delete("/{collection_id}")
def delete_collection(collection_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM collections WHERE id = :id AND user_id = :uid"), {"id": collection_id, "uid": user_id})
    db.commit()
    return {"message": "deleted"}

@router.post("/{collection_id}/books")
def add_book_to_collection(collection_id: str, body: AddBookToCollection, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    col = db.execute(text("SELECT id FROM collections WHERE id = :id AND user_id = :uid"), {"id": collection_id, "uid": user_id}).fetchone()
    if not col:
        raise HTTPException(status_code=404, detail="合集不存在")
    db.execute(text(
        "INSERT IGNORE INTO collection_books (collection_id, user_book_id) VALUES (:cid, :bid)"
    ), {"cid": collection_id, "bid": body.user_book_id})
    db.commit()
    return {"message": "added"}

@router.delete("/{collection_id}/books/{user_book_id}")
def remove_book_from_collection(collection_id: str, user_book_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    db.execute(text(
        "DELETE FROM collection_books WHERE collection_id = :cid AND user_book_id = :bid"
    ), {"cid": collection_id, "bid": user_book_id})
    db.commit()
    return {"message": "removed"}
