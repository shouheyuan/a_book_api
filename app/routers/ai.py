import uuid, json
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List, Any
from sse_starlette.sse import EventSourceResponse
from openai import AsyncOpenAI
import os
import httpx
from app.db import get_db
from app.core.auth import get_current_user_id
from app.core.prompt_builder import build_optimize_prompt

# Setup Custom AI Client
ai_client = AsyncOpenAI(
    api_key=os.environ.get("NEW_API_KEY", ""),
    base_url="http://180.184.59.27:18887/v1"
)

router = APIRouter()

class AIImageRecord(BaseModel):
    book_id: Optional[str] = None
    paragraph_id: str
    prompt: Optional[str] = None
    image_urls: Optional[List[str]] = []
    locator: Optional[dict] = None
    source_language: Optional[str] = "zh-Hans"

class AIRevisionRecord(BaseModel):
    book_identifier: Optional[str] = None
    paragraph_id: str
    original_text: str
    revised_versions: Optional[List[str]] = []
    locator: Optional[dict] = None
    source_language: Optional[str] = "zh-Hans"

class AIReviseGenerateRequest(BaseModel):
    original_text: str
    style: str
    params: Optional[dict] = {}
    source_language: Optional[str] = "zh-Hans"

class AIGenerateImageRequest(BaseModel):
    prompt: str
    size: Optional[str] = "2K"
    source_language: Optional[str] = "zh-Hans"

@router.post("/images/generate")
async def generate_image(body: AIGenerateImageRequest, user_id: str = Depends(get_current_user_id)):
    """
    调用火山引擎 (Volcengine) Doubao Seedream 生成图片
    """
    from fastapi import HTTPException
    volcengine_key = os.environ.get("VOLCENGINE_API_KEY")
    if not volcengine_key:
        raise HTTPException(status_code=500, detail="Volcengine API key not configured")

    url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {volcengine_key}"
    }
    payload = {
        "model": "doubao-seedream-5-0-260128",
        "prompt": body.prompt,
        "sequential_image_generation": "disabled",
        "response_format": "url",
        "size": body.size,
        "stream": False,
        "watermark": True
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=60.0)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            error_msg = exc.response.text
            # 始终向前端返回 502，以明确是“上游服务出错”，而非前端的身份验证已过期 (401)
            raise HTTPException(status_code=502, detail=f"Volcengine API Error: {error_msg}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.post("/revisions/generate")
async def generate_revision(body: AIReviseGenerateRequest, user_id: str = Depends(get_current_user_id)):
    """
    流式返回根据优化提示词执行的 AI 改文结果
    """
    # 1. 获取用户信息 (预留属性)
    mock_user_info = {"persona": "无特别偏好"} # 待接真实 DB

    # 2. 生成多维度优化的 Prompt
    params_for_prompt = {"style": body.style}
    if body.params:
        params_for_prompt.update(body.params)
        
    messages = build_optimize_prompt(mock_user_info, body.original_text, params_for_prompt, body.source_language)

    # 3. 请求大模型 (流式)
    async def generate():
        is_thinking = False
        try:
            response = await ai_client.chat.completions.create(
                model="Doubao-Seed-2.0-lite-32k",
                messages=messages,
                stream=True,
                extra_body={
                    "thinking_type": "disabled"
                }
            )
            async for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None) or ""
                
                if content:
                    if "<think>" in content:
                        is_thinking = True
                        content = content.replace("<think>", "")
                    
                    if "</think>" in content:
                        is_thinking = False
                        content = content.split("</think>")[-1]
                    
                    # 当前在包裹区域内时，清空 content 内容
                    if is_thinking:
                        content = ""
                        
                    if content:
                        yield {"data": content}
        except Exception as e:
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(generate())

@router.post("/images")
def record_ai_image(body: AIImageRecord, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rec_id = str(uuid.uuid4())
    loc_val = json.dumps(body.locator) if body.locator else None
    db.execute(text(
        "INSERT INTO ai_images (id, user_id, book_id, paragraph_id, prompt, image_urls, locator) "
        "VALUES (:id, :uid, :bid, :pid, :prompt, :urls, :loc)"
    ), {"id": rec_id, "uid": user_id, "bid": body.book_id, "pid": body.paragraph_id,
        "prompt": body.prompt, "urls": json.dumps(body.image_urls), "loc": loc_val})
    db.commit()
    return {"id": rec_id, "message": "recorded"}

@router.get("/images")
def get_ai_images(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT * FROM ai_images WHERE user_id = :uid ORDER BY created_at DESC"
    ), {"uid": user_id}).fetchall()
    result = []
    for r in rows:
        d = dict(r._mapping)
        if d.get("image_urls") and isinstance(d["image_urls"], str):
            d["image_urls"] = json.loads(d["image_urls"])
        if d.get("locator") and isinstance(d["locator"], str):
            try:
                d["locator"] = json.loads(d["locator"])
            except:
                d["locator"] = None
        result.append(d)
    return result

@router.delete("/images/{id}")
def delete_ai_image(id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    result = db.execute(text(
        "DELETE FROM ai_images WHERE id = :id AND user_id = :uid"
    ), {"id": id, "uid": user_id})
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Generation not found or unauthorized")
    return {"message": "deleted"}

@router.post("/revisions")
def record_ai_revision(body: AIRevisionRecord, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    # Check if a record for this paragraph already exists for this user
    existing_id = db.execute(text(
        "SELECT id FROM ai_revisions WHERE user_id = :uid AND paragraph_id = :pid"
    ), {"uid": user_id, "pid": body.paragraph_id}).scalar()

    loc_val = json.dumps(body.locator) if body.locator else None

    if existing_id:
        db.execute(text(
            "UPDATE ai_revisions SET revised_versions = :revs, book_identifier = :bid, locator = :loc WHERE id = :id"
        ), {"id": existing_id, "revs": json.dumps(body.revised_versions), "bid": body.book_identifier, "loc": loc_val})
        rec_id = existing_id
    else:
        rec_id = str(uuid.uuid4())
        db.execute(text(
            "INSERT INTO ai_revisions (id, user_id, book_identifier, paragraph_id, original_text, revised_versions, locator) "
            "VALUES (:id, :uid, :bid, :pid, :orig, :revs, :loc)"
        ), {"id": rec_id, "uid": user_id, "bid": body.book_identifier, "pid": body.paragraph_id,
            "orig": body.original_text, "revs": json.dumps(body.revised_versions), "loc": loc_val})
    
    db.commit()
    return {"id": rec_id, "message": "recorded"}

@router.get("/revisions")
def get_ai_revisions(user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    rows = db.execute(text(
        "SELECT * FROM ai_revisions WHERE user_id = :uid ORDER BY created_at DESC"
    ), {"uid": user_id}).fetchall()
    result = []
    for r in rows:
        d = dict(r._mapping)
        if d.get("revised_versions") and isinstance(d["revised_versions"], str):
            d["revised_versions"] = json.loads(d["revised_versions"])
        if d.get("locator") and isinstance(d["locator"], str):
            try:
                d["locator"] = json.loads(d["locator"])
            except:
                d["locator"] = None
        result.append(d)
    return result

@router.delete("/revisions/{id}")
def delete_ai_revision(id: str, user_id: str = Depends(get_current_user_id), db: Session = Depends(get_db)):
    result = db.execute(text(
        "DELETE FROM ai_revisions WHERE id = :id AND user_id = :uid"
    ), {"id": id, "uid": user_id})
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Revision not found or unauthorized")
    return {"message": "deleted"}
