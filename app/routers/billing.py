import uuid
import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from app.db import get_db
from app.core.auth import get_current_user_id

router = APIRouter()

class TransactionRequest(BaseModel):
    amount: int                        # 正数=充值/赠予, 负数=消费
    type: str                          # e.g. "recharge", "spend", "daily_bonus", "ai_generation"
    description: Optional[str] = None
    is_gift: Optional[bool] = False    # 如果为 true，正数时加到 monthly_coin_balance 否则加到 coin_balance

@router.get("/transactions")
def get_transactions(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT * FROM coin_transactions WHERE user_id = :uid ORDER BY created_at DESC"
    ), {"uid": user_id}).fetchall()
    return [dict(r._mapping) for r in rows]

@router.post("/transactions")
def create_transaction(body: TransactionRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    profile = db.execute(text("SELECT coin_balance, monthly_coin_balance FROM user_profiles WHERE id = :id"), {"id": user_id}).fetchone()
    
    current_coin = profile.coin_balance if profile and profile.coin_balance else 0
    current_monthly = profile.monthly_coin_balance if profile and profile.monthly_coin_balance else 0

    if body.amount < 0:
        # 扣费逻辑：允许负费消耗。只要总余额 > 0 即可放行扣费，即使扣完变负数。
        # 如果总余额已经 <= 0，则真正拦截不再允许使用 AI。
        deduct = abs(body.amount)
        if current_monthly + current_coin <= 0:
            return JSONResponse(status_code=400, content={
                "error_code": "insufficient_points",
                "detail": "账户魔力值处于欠费状态，暂无法使用 AI 创作功能。快去充值或参与签到获取魔力值吧！✨"
            })
        
        # 优先扣除限时赠币，剩下的（包括透支的部分）扣在永久币上
        deduct_from_monthly = min(max(current_monthly, 0), deduct)
        deduct_from_coin = deduct - deduct_from_monthly
        
        new_monthly = current_monthly - deduct_from_monthly
        new_coin = current_coin - deduct_from_coin
    else:
        # 加钱逻辑：如果目前存在负债（欠费），无论是充值还是赠予，优先填平欠款！
        remaining_recharge = body.amount
        new_coin = current_coin
        new_monthly = current_monthly

        if new_coin < 0:
            payoff = min(abs(new_coin), remaining_recharge)
            new_coin += payoff
            remaining_recharge -= payoff

        # 填平欠帐后，剩余金额按类型分配
        if body.is_gift:
            new_monthly += remaining_recharge
        else:
            new_coin += remaining_recharge

    balance_after = new_monthly + new_coin
    tx_id = str(uuid.uuid4())
    
    # 同一事务内同步写流水 + 更新余额
    db.execute(text(
        "INSERT INTO coin_transactions (id, user_id, amount, type, description, balance_after) VALUES (:id,:uid,:amount,:type,:desc,:bal)"
    ), {"id": tx_id, "uid": user_id, "amount": body.amount, "type": body.type, "desc": body.description, "bal": balance_after})
    
    db.execute(text(
        "UPDATE user_profiles SET coin_balance = :coin, monthly_coin_balance = :monthly, updated_at = NOW() WHERE id = :id"
    ), {"coin": new_coin, "monthly": new_monthly, "id": user_id})
    db.commit()
    return {"id": tx_id, "balance_after": balance_after}

import os

IS_DEV = os.environ.get("IS_DEV", "True").lower() == "true"

class AppleVerifyRequest(BaseModel):
    transaction_id: str
    jws: str

@router.post("/apple/verify")
def verify_apple_receipt(body: AppleVerifyRequest, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    try:
        if IS_DEV:
            # 开发环境：绕过苹果的正式公钥强签名校验，直接解包 Base64 提取 payload
            payload = jwt.decode(body.jws, options={"verify_signature": False})
        else:
            # 生产环境：需要向苹果 App Store Server Request 或者加载苹果根证书进行严格的 verify_signature=True
            # 这里留出正式接口占位，目前若强行验证会报错
            raise HTTPException(status_code=500, detail="Production signature verification not yet implemented. Set IS_DEV=True")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JWS format: {str(e)}")
        
    product_id = payload.get("productId")
    if not product_id:
        raise HTTPException(status_code=400, detail="No productId found in transaction")
        
    # Check if duplicate in coin_transactions
    existing = db.execute(text("SELECT id FROM coin_transactions WHERE reference_id = :ref"), {"ref": body.transaction_id}).fetchone()
    if existing:
        return {"message": "Already processed", "status": "success"}

    profile = db.execute(text("SELECT coin_balance FROM user_profiles WHERE id = :id"), {"id": user_id}).fetchone()
    current_balance = profile.coin_balance if profile and profile.coin_balance else 0

    # Determine product type
    if "energy" in product_id:
        try:
            # e.g., product_id = "com.visionnovel.energy.30" -> tier is 30, amount is 300
            tier = int(product_id.split(".")[-1])
            amount = tier * 10
        except:
            amount = 100
        new_balance = current_balance + amount
        tx_id = str(uuid.uuid4())
        
        # INSERT TRANSACTION
        db.execute(text(
            "INSERT INTO coin_transactions (id, user_id, amount, type, description, reference_id, balance_after) VALUES (:id,:uid,:amount,:type,:desc,:ref,:bal)"
        ), {"id": tx_id, "uid": user_id, "amount": amount, "type": "recharge", "desc": f"Purchased {product_id}", "ref": body.transaction_id, "bal": new_balance})
        
        # UPDATE BALANCE
        db.execute(text(
            "UPDATE user_profiles SET coin_balance = :bal, updated_at = NOW() WHERE id = :id"
        ), {"bal": new_balance, "id": user_id})
        
    elif "vip" in product_id:
        # Give VIP
        tx_id = str(uuid.uuid4())
        
        db.execute(text(
            "INSERT INTO coin_transactions (id, user_id, amount, type, description, reference_id, balance_after) VALUES (:id,:uid,:amount,:type,:desc,:ref,:bal)"
        ), {"id": tx_id, "uid": user_id, "amount": 0, "type": "vip_subscription", "desc": f"Purchased {product_id}", "ref": body.transaction_id, "bal": current_balance})
        
        plan_type = "monthly"
        duration_sql = "INTERVAL 1 MONTH"
        if "quarterly" in product_id:
            plan_type, duration_sql = "quarterly", "INTERVAL 3 MONTH"
        elif "yearly" in product_id:
            plan_type, duration_sql = "yearly", "INTERVAL 1 YEAR"
        elif "lifetime" in product_id:
            plan_type, duration_sql = "lifetime", "INTERVAL 99 YEAR"

        db.execute(text(
            f"UPDATE user_profiles SET is_vip = TRUE, vip_plan_type = :ptype, vip_expires_at = DATE_ADD(IFNULL(vip_expires_at, NOW()), {duration_sql}), updated_at = NOW() WHERE id = :id"
        ), {"id": user_id, "ptype": plan_type})
        
    db.commit()
    return {"message": "Purchase verified and items given"}

class AppleWebhookRequest(BaseModel):
    signedPayload: str

@router.post("/apple/webhook")
def apple_webhook(body: AppleWebhookRequest, db: Session = Depends(get_db)):
    """
    Handles Apple App Store Server Notifications V2 (S2S Webhook).
    Specifically captures auto-renewals using the `appAccountToken` (Option A).
    """
    try:
        # Decode the main payload
        payload = jwt.decode(body.signedPayload, options={"verify_signature": False})
        notification_type = payload.get("notificationType")
        
        # Extract signed transaction info
        data = payload.get("data", {})
        signed_txn = data.get("signedTransactionInfo")
        if not signed_txn:
            return {"status": "ok", "message": "No transaction info"}
            
        txn_data = jwt.decode(signed_txn, options={"verify_signature": False})
        app_account_token = txn_data.get("appAccountToken")
        transaction_id = txn_data.get("transactionId")
        product_id = txn_data.get("productId")
        
        # Without appAccountToken, we cannot link the renewal to a specific user here
        if not app_account_token:
            return {"status": "ok", "message": "Missing appAccountToken"}
            
        # We only process DID_RENEW and SUBSCRIBED for simplicity
        if notification_type not in ["DID_RENEW", "SUBSCRIBED"]:
            return {"status": "ok", "message": f"Ignored notificationType: {notification_type}"}

        # Check if we already processed this unique transaction from Apple
        existing = db.execute(text("SELECT id FROM coin_transactions WHERE reference_id = :ref"), {"ref": transaction_id}).fetchone()
        if existing:
            return {"status": "ok", "message": "Already processed"}

        user_id = str(app_account_token)
        profile = db.execute(text("SELECT id, coin_balance FROM user_profiles WHERE id = :id"), {"id": user_id}).fetchone()
        if not profile:
            return {"status": "ok", "message": "User not found"}
            
        # Grant VIP benefits
        if "vip" in product_id:
            tx_id = str(uuid.uuid4())
            curr_balance = profile.coin_balance if profile.coin_balance else 0
            
            db.execute(text(
                "INSERT INTO coin_transactions (id, user_id, amount, type, description, reference_id, balance_after) VALUES (:id,:uid,:amount,:type,:desc,:ref,:bal)"
            ), {"id": tx_id, "uid": user_id, "amount": 0, "type": "vip_auto_renew", "desc": f"Auto-renewed {product_id} ({notification_type})", "ref": transaction_id, "bal": curr_balance})
            
            plan_type = "monthly"
            duration_sql = "INTERVAL 1 MONTH"
            if "quarterly" in product_id:
                plan_type, duration_sql = "quarterly", "INTERVAL 3 MONTH"
            elif "yearly" in product_id:
                plan_type, duration_sql = "yearly", "INTERVAL 1 YEAR"
            elif "lifetime" in product_id:
                plan_type, duration_sql = "lifetime", "INTERVAL 99 YEAR"

            db.execute(text(
                f"UPDATE user_profiles SET is_vip = TRUE, vip_plan_type = :ptype, vip_expires_at = DATE_ADD(IFNULL(vip_expires_at, NOW()), {duration_sql}), updated_at = NOW() WHERE id = :id"
            ), {"id": user_id, "ptype": plan_type})
            
            db.commit()
            
    except Exception as e:
        print(f"Apple Webhook processing error: {e}")
        # Always return 200/OK so Apple stops retrying, unless you want them to retry on transient db errors
        
    return {"status": "ok"}
