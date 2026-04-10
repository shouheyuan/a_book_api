from jose import jwt
import bcrypt
from datetime import datetime, timedelta
from fastapi import Header, HTTPException
import os

def hash_password(pw: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=int(os.getenv("JWT_EXPIRE_MINUTES", 10080)))
    return jwt.encode(
        {"sub": user_id, "exp": expire},
        os.getenv("JWT_SECRET"),
        algorithm=os.getenv("JWT_ALGORITHM", "HS256")
    )

def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token 未提供")
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(
            token,
            os.getenv("JWT_SECRET"),
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")]
        )
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
