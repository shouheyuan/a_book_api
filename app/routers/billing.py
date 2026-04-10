import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.db import get_db
from app.core.auth import get_current_user_id

router = APIRouter()

class TransactionRequest(BaseModel):
    amount: int                        # 正数=充值, 负数=消费
    type: str                          # e.g. "recharge", "spend", "refund"
    description: Optional[str] = None

@router.get("/transactions")
def get_transactions(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT * FROM coin_transactions WHERE user_id = :uid ORDER BY created_at DESC"
    ), {"uid": user_id}).fetchall()
    return [dict(r._mapping) for r in rows]

@router.post("/transactions")
def create_transaction(body: TransactionRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    profile = db.execute(text("SELECT coin_balance FROM user_profiles WHERE id = :id"), {"id": user_id}).fetchone()
    new_balance = profile.coin_balance + body.amount
    if new_balance < 0:
        raise HTTPException(status_code=400, detail="书币余额不足")
    tx_id = str(uuid.uuid4())
    # 同一事务内同步写流水 + 更新余额
    db.execute(text(
        "INSERT INTO coin_transactions (id, user_id, amount, type, description) VALUES (:id,:uid,:amount,:type,:desc)"
    ), {"id": tx_id, "uid": user_id, "amount": body.amount, "type": body.type, "desc": body.description})
    db.execute(text(
        "UPDATE user_profiles SET coin_balance = :bal, updated_at = NOW() WHERE id = :id"
    ), {"bal": new_balance, "id": user_id})
    db.commit()
    return {"id": tx_id, "balance_after": new_balance}
