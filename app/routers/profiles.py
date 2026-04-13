from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.db import get_db
from app.core.auth import get_current_user_id
from app.utils.storage import save_avatar

router = APIRouter()

class ProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    bio: Optional[str] = None
    signature: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[str] = None
    preferences: Optional[str] = None
    avatar_url: Optional[str] = None
    avatarUrl: Optional[str] = None

@router.get("/profiles/me")
def get_profile(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = db.execute(text(
        "SELECT id, email, nickname, bio, signature, gender, age, preferences, avatar_url, coin_balance, monthly_coin_balance, is_vip, vip_expires_at, created_at FROM user_profiles WHERE id = :id"
    ), {"id": user_id}).fetchone()
    # Serialize datetime to standard string format
    result = dict(row._mapping)
    if result.get("is_vip") is not None:
        result["is_vip"] = bool(result["is_vip"])
    if result.get("vip_expires_at"):
        result["vip_expires_at"] = result["vip_expires_at"].isoformat()
    if result.get("created_at"):
        result["created_at"] = result["created_at"].isoformat()
    return result

@router.patch("/profiles/me")
def update_profile(body: ProfileUpdate, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    fields = {}
    if body.nickname is not None: fields["nickname"] = body.nickname
    if body.bio is not None: fields["bio"] = body.bio
    if body.signature is not None: fields["signature"] = body.signature
    if body.gender is not None: fields["gender"] = body.gender
    if body.age is not None: fields["age"] = body.age
    if body.preferences is not None: fields["preferences"] = body.preferences
    if body.avatar_url is not None: fields["avatar_url"] = body.avatar_url
    if body.avatarUrl is not None: fields["avatar_url"] = body.avatarUrl

    if not fields:
        return {"message": "no changes"}
    set_clause = ", ".join(f"{k} = :{k}" for k in fields)
    fields["id"] = user_id
    db.execute(text(f"UPDATE user_profiles SET {set_clause}, updated_at = NOW() WHERE id = :id"), fields)
    db.commit()
    return {"message": "updated"}

@router.post("/profiles/avatar")
async def upload_avatar(file: UploadFile = File(...), user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    url = await save_avatar(file, user_id)
    db.execute(text("UPDATE user_profiles SET avatar_url = :url, updated_at = NOW() WHERE id = :id"), {"url": url, "id": user_id})
    db.commit()
    return {"avatar_url": url}

@router.get("/profiles/me/stats")
def get_stats(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    row = db.execute(text("""
        SELECT
            (SELECT COUNT(*) FROM reading_sessions WHERE user_id = :uid) AS books_read_count,
            (SELECT COUNT(*) FROM annotations WHERE user_id = :uid) AS notes_count,
            (SELECT COUNT(*) FROM ai_images WHERE user_id = :uid) AS ai_generations_count,
            (SELECT COUNT(*) FROM ai_revisions WHERE user_id = :uid) AS ai_revisions_count
    """), {"uid": user_id}).fetchone()
    return dict(row._mapping)
