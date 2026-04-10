# 🐍 VisionNovel - Python 后端开发文档

## 快速启动

```bash
pip install fastapi uvicorn PyMySQL SQLAlchemy passlib[bcrypt] python-jose python-multipart python-dotenv
uvicorn main:app --reload --port 8000
```

访问 `http://localhost:8000/docs` 查看 Swagger 接口调试页面。

---

## 推荐目录结构

```
visionnovel-backend/
├── main.py
├── .env
├── app/
│   ├── db.py            # MySQL 连接
│   ├── core/auth.py     # JWT + bcrypt
│   ├── utils/storage.py # 文件上传
│   └── routers/
│       ├── auth.py
│       ├── profiles.py
│       ├── reading.py
│       ├── annotations.py
│       ├── books.py
│       ├── ai.py
│       ├── billing.py
│       └── collections.py
└── static/avatars/
```

---

## .env 配置

```dotenv
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=123456
DB_NAME=visionnovel

JWT_SECRET=your_long_random_secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080

BASE_URL=http://localhost:8000
STATIC_DIR=./static
```

---

## 数据库连接（app/db.py）

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}?charset=utf8mb4"
)
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## JWT 身份验证（app/core/auth.py）

```python
from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from fastapi import Header, HTTPException
import os

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=int(os.getenv("JWT_EXPIRE_MINUTES", 10080)))
    return jwt.encode({"sub": user_id, "exp": expire}, os.getenv("JWT_SECRET"), algorithm="HS256")

def get_current_user_id(authorization: str = Header(...)) -> str:
    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        return payload["sub"]
    except Exception:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
```

---

## 文件上传（app/utils/storage.py）

```python
import os, uuid
from fastapi import UploadFile

async def save_avatar(file: UploadFile, user_id: str) -> str:
    static_dir = os.getenv("STATIC_DIR", "./static")
    ext = file.filename.split(".")[-1]
    filename = f"{user_id}_{uuid.uuid4().hex}.{ext}"
    path = os.path.join(static_dir, "avatars", filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(await file.read())
    return f"{os.getenv('BASE_URL')}/static/avatars/{filename}"
```

---

## 程序入口（main.py）

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routers import auth, profiles, reading, annotations, books, ai, billing, collections

app = FastAPI(title="VisionNovel API", version="1.0")
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router,        prefix="/v1/auth",             tags=["Auth"])
app.include_router(profiles.router,    prefix="/v1",                  tags=["Profiles"])
app.include_router(reading.router,     prefix="/v1/reading-sessions", tags=["Reading"])
app.include_router(annotations.router, prefix="/v1/annotations",      tags=["Annotations"])
app.include_router(books.router,       prefix="/v1",                  tags=["Books"])
app.include_router(ai.router,          prefix="/v1/ai",               tags=["AI"])
app.include_router(billing.router,     prefix="/v1/billing",          tags=["Billing"])
app.include_router(collections.router, prefix="/v1/collections",      tags=["Collections"])
```

---

## API 接口总览

| 模块 | 方法 | 路径 | 说明 |
|-|-|-|-|
| 认证 | POST | `/v1/auth/signup` | 注册 |
| | POST | `/v1/auth/signin` | 登录 |
| | POST | `/v1/auth/apple` | Apple 登录 |
| 用户 | GET | `/v1/profiles/me` | 获取资料 |
| | PATCH | `/v1/profiles/me` | 更新资料 |
| | POST | `/v1/profiles/avatar` | 上传头像 |
| 统计 | GET | `/v1/users/me/stats` | 四项统计 |
| 阅读 | POST | `/v1/reading-sessions` | 同步进度 |
| | GET | `/v1/reading-sessions` | 获取全部 |
| | DELETE | `/v1/reading-sessions/{book_identifier}` | 删除进度 |
| 笔记 | POST | `/v1/annotations` | 同步笔记 |
| | GET | `/v1/annotations` | 获取全部 |
| | DELETE | `/v1/annotations/{id}` | 删除单条 |
| | DELETE | `/v1/annotations/book/{book_identifier}` | 删除整本 |
| AI | POST | `/v1/ai/images` | 记录生图 |
| | GET | `/v1/ai/images` | 查询生图 |
| | POST | `/v1/ai/revisions` | 记录改写 |
| | GET | `/v1/ai/revisions` | 查询改写 |
| 书库 | GET | `/v1/books` | 搜索书库 |
| | POST | `/v1/bookshelf` | 加入书架 |
| | GET | `/v1/bookshelf` | 我的书架 |
| | DELETE | `/v1/bookshelf/{book_id}` | 移出书架 |
| 合集 | POST | `/v1/collections` | 创建合集 |
| | GET | `/v1/collections` | 合集列表 |
| | DELETE | `/v1/collections/{id}` | 删除合集 |
| | POST | `/v1/collections/{id}/books` | 加书进合集 |
| | DELETE | `/v1/collections/{id}/books/{user_book_id}` | 移书出合集 |
| 书币 | GET | `/v1/billing/transactions` | 流水记录 |
| | POST | `/v1/billing/transactions` | 记录消费 |

---

## 注意事项

1. **UUID 主键**：用 Python 的 `str(uuid.uuid4())` 生成，不要依赖 MySQL 自动生成。
2. **JSON 字段**：`locator_json` 等字段存入用 `json.dumps()`，读出用 `json.loads()`。
3. **书币一致性**：写 `coin_transactions` 时，同一事务内要同步更新 `user_profiles.coin_balance`。
4. **统计接口**：`/v1/users/me/stats` 用 SQL `COUNT` 聚合，不要分四次 Python 查询。
