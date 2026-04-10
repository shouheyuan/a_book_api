import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.db import get_db
from app.core.auth import hash_password, verify_password, create_token

router = APIRouter()

class SignupRequest(BaseModel):
    email: str
    password: str
    nickname: Optional[str] = None

class SigninRequest(BaseModel):
    email: str
    password: str

class AppleLoginRequest(BaseModel):
    identity_token: str
    user_id: str
    email: Optional[str] = None
    full_name: Optional[str] = None

@router.post("/signup")
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    row = db.execute(text("SELECT id FROM user_profiles WHERE email = :email"), {"email": body.email}).fetchone()
    if row:
        raise HTTPException(status_code=409, detail="该邮箱已注册")
    user_id = str(uuid.uuid4())
    db.execute(text(
        "INSERT INTO user_profiles (id, email, nickname, password_hash, coin_balance, monthly_coin_balance) "
        "VALUES (:id, :email, :nickname, :pw, 0, 0)"
    ), {"id": user_id, "email": body.email, "nickname": body.nickname or body.email.split("@")[0], "pw": hash_password(body.password)})
    db.commit()
    return {"token": create_token(user_id), "user": {"id": user_id, "email": body.email}}

@router.post("/signin")
def signin(body: SigninRequest, db: Session = Depends(get_db)):
    row = db.execute(text("SELECT id, email, password_hash FROM user_profiles WHERE email = :email"), {"email": body.email}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(body.password, row.password_hash):
        raise HTTPException(status_code=401, detail="密码错误")
    return {"token": create_token(row.id), "user": {"id": row.id, "email": row.email}}

@router.post("/apple")
def apple_login(body: AppleLoginRequest, db: Session = Depends(get_db)):
    email = body.email or f"{body.user_id}@privaterelay.appleid.com"
    row = db.execute(text("SELECT id, email FROM user_profiles WHERE email = :email"), {"email": email}).fetchone()
    if row:
        return {"token": create_token(row.id), "user": {"id": row.id, "email": row.email}}
    user_id = str(uuid.uuid4())
    db.execute(text(
        "INSERT INTO user_profiles (id, email, nickname, password_hash, coin_balance, monthly_coin_balance) "
        "VALUES (:id, :email, :nickname, :pw, 0, 0)"
    ), {"id": user_id, "email": email, "nickname": body.full_name or "Apple User", "pw": hash_password(str(uuid.uuid4()))})
    db.commit()
    return {"token": create_token(user_id), "user": {"id": user_id, "email": email}}

@router.post("/reset-password")
def reset_password(body: SigninRequest, db: Session = Depends(get_db)):
    row = db.execute(text("SELECT id FROM user_profiles WHERE email = :email"), {"email": body.email}).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="邮箱尚未注册")
    db.execute(text(
        "UPDATE user_profiles SET password_hash = :pw WHERE email = :email"
    ), {"pw": hash_password(body.password), "email": body.email})
    db.commit()
    return {"message": "密码重置成功"}
