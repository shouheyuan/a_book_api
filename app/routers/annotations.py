import uuid, json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, Any, List, Union
from app.db import get_db
from app.core.auth import get_current_user_id

router = APIRouter()

class AnnotationItem(BaseModel):
    id: Optional[str] = None
    book_identifier: str
    book_title: Optional[str] = None
    cover_path: Optional[str] = None
    text: str
    note: Optional[str] = None
    locator: Any          # JSON object
    color: Optional[str] = "yellow"

def _upsert_annotation(ann: AnnotationItem, user_id: str, db: Session):
    ann_id = ann.id or str(uuid.uuid4())
    locator = json.dumps(ann.locator) if ann.locator is not None else "{}"
    existing = db.execute(text("SELECT id FROM annotations WHERE id = :id"), {"id": ann_id}).fetchone()
    if existing:
        db.execute(text(
            "UPDATE annotations SET text=:txt, note=:note, locator=:loc, color=:color, "
            "book_title=:title, cover_path=:cover WHERE id=:id AND user_id=:uid"
        ), {"txt": ann.text, "note": ann.note, "loc": locator, "color": ann.color,
            "title": ann.book_title, "cover": ann.cover_path, "id": ann_id, "uid": user_id})
    else:
        db.execute(text(
            "INSERT INTO annotations (id, user_id, book_identifier, book_title, cover_path, text, note, locator, color) "
            "VALUES (:id,:uid,:bid,:title,:cover,:txt,:note,:loc,:color)"
        ), {"id": ann_id, "uid": user_id, "bid": ann.book_identifier, "title": ann.book_title,
            "cover": ann.cover_path, "txt": ann.text, "note": ann.note, "loc": locator, "color": ann.color})
    return ann_id

# Swift 调用的是单条 POST（payload 是 dict，不是 list）
@router.post("")
async def sync_annotations(request: Request, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    body = await request.json()
    # 支持单条 dict 和批量 list 两种格式
    items = body if isinstance(body, list) else [body]
    ids = []
    for item in items:
        ann = AnnotationItem(**item)
        ann_id = _upsert_annotation(ann, user_id, db)
        ids.append(ann_id)
    db.commit()
    return {"message": "synced", "count": len(ids), "ids": ids}

@router.get("")
def get_annotations(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT * FROM annotations WHERE user_id = :uid ORDER BY created_at DESC"
    ), {"uid": user_id}).fetchall()
    
    result = []
    for r in rows:
        d = dict(r._mapping)
        if d.get("locator") and isinstance(d["locator"], str):
            try:
                d["locator"] = json.loads(d["locator"])
            except Exception:
                pass
        if d.get("created_at"):
            d["created_at"] = d["created_at"].isoformat()
        if d.get("updated_at"):
            d["updated_at"] = d["updated_at"].isoformat()
        result.append(d)
    return result

@router.delete("/{annotation_id}")
def delete_annotation(annotation_id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    db.execute(text("DELETE FROM annotations WHERE id = :id AND user_id = :uid"), {"id": annotation_id, "uid": user_id})
    db.commit()
    return {"message": "deleted"}

@router.delete("/book/{book_identifier}")
def delete_book_annotations(book_identifier: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    db.execute(text(
        "DELETE FROM annotations WHERE book_identifier = :bid AND user_id = :uid"
    ), {"bid": book_identifier, "uid": user_id})
    db.commit()
    return {"message": "deleted"}
