import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sse_starlette.sse import EventSourceResponse
from openai import AsyncOpenAI
import os

from app.db import get_db
from app.core.auth import get_current_user_id
from app.core.i18n import get_language, t

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatStreamRequest(BaseModel):
    mode: str = "standard"  # "standard" | "search" | "roleplay"
    book_identifier: Optional[str] = None
    character_id: Optional[str] = None
    local_context: Optional[str] = None
    message: str
    history: Optional[List[ChatMessage]] = []

# ---------------------------------------------------------------------------
# Context Retrieval Helpers
# ---------------------------------------------------------------------------

def fetch_user_bookshelf_context(user_id: str, book_identifier: Optional[str], db: Session) -> str:
    """Retrieves user's reading context (annotations, progress) from DB."""
    context_lines = []
    
    if book_identifier:
        # Get book title
        book_row = db.execute(text("SELECT title, author FROM books WHERE identifier = :bid"), {"bid": book_identifier}).fetchone()
        if book_row:
            context_lines.append(f"【当前阅读的书籍】：《{book_row[0]}》 作者：{book_row[1]}")
        
        # Get latest annotations
        ann_rows = db.execute(
            text("SELECT text, note FROM annotations WHERE user_id=:uid AND book_identifier=:bid ORDER BY created_at DESC LIMIT 10"),
            {"uid": user_id, "bid": book_identifier}
        ).fetchall()
        
        if ann_rows:
            context_lines.append("【用户最近的高亮与笔记】：")
            for r in ann_rows:
                context_lines.append(f"- 原文段落: \"{r[0]}\" | 用户笔记: \"{r[1] or '无'}\"")
                
    else:
        # General bookshelf summary
        book_rows = db.execute(
            text("SELECT title FROM books LIMIT 5")
        ).fetchall()
        if book_rows:
            titles = "、".join([r[0] for r in book_rows])
            context_lines.append(f"【用户的书架】：最近在读 {titles}")

    return "\n".join(context_lines)

def fetch_character_context(user_id: str, character_id: str, db: Session) -> Optional[dict]:
    """Retrieves character persona from lore_entities table."""
    row = db.execute(
        text("SELECT name, aliases, appearance_desc, persona_desc FROM lore_entities WHERE (id=:id OR name=:id) AND user_id=:uid LIMIT 1"),
        {"id": character_id, "uid": user_id}
    ).fetchone()
    
    if row:
        return {
            "name": row[0],
            "aliases": row[1],
            "appearance_desc": row[2],
            "persona_desc": row[3]
        }
    return None

# ---------------------------------------------------------------------------
# Prompt Assembly
# ---------------------------------------------------------------------------

def build_system_prompt(mode: str, context_data: dict) -> str:
    if mode == "roleplay":
        char = context_data.get("character", {})
        return f"""【系统指令】
你现在必须完全沉浸式地扮演以下角色。你绝对不能承认自己是AI助手。
你的名字：{char.get("name", "未知")}
你的外貌与特征：{char.get("appearance_desc", "未知")}
你的性格与人设：{char.get("persona_desc", "未知")}

请严格按照上述性格特点、语气和口癖与用户进行第一人称对话。如果用户问及书外的事情，请用符合你身份的认知来回答，或者表示听不懂。
"""

    else: # standard
        bookshelf_ctx = context_data.get("bookshelf", "")
        local_ctx = context_data.get("local_context", "")
        base_prompt = """你是 VisionNovel 的专属阅读助理，同时也是强大的智能搜索助理。
你的任务是帮助用户更好地理解他们正在阅读的内容，解答剧情疑问，并可以结合用户的私人笔记进行深度探讨。
你也可以直接解答用户关于书籍背景、评价、作者生平、传记推荐等问题。请尽可能提供客观、全面且有价值的信息。
"""
        if bookshelf_ctx or local_ctx:
            base_prompt += f"\n以下是系统为你提供的用户专属阅读上下文，请在回答时参考（如无关则忽略）：\n{bookshelf_ctx}\n{local_ctx}\n"
        return base_prompt

# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post("/stream")
async def chat_stream(
    req: ChatStreamRequest, 
    user_id: str = Depends(get_current_user_id), 
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    """
    流式全局 AI 问答接口，支持三种模式：standard (书架上下文), search (联网), roleplay (角色扮演)
    """
    context_data = {}
    
    # 1. Fetch Context based on Mode
    if req.mode == "roleplay":
        if not req.character_id:
            raise HTTPException(status_code=400, detail=t("error_character_id_required", lang))
        char_info = fetch_character_context(user_id, req.character_id, db)
        if not char_info:
            raise HTTPException(status_code=404, detail=t("error_character_not_found", lang))
        context_data["character"] = char_info
        
    elif req.mode == "standard":
        context_data["bookshelf"] = fetch_user_bookshelf_context(user_id, req.book_identifier, db)
        
    if req.local_context:
        context_data["local_context"] = req.local_context

    # 2. Assemble Messages
    system_prompt = build_system_prompt(req.mode, context_data)
    
    messages = [{"role": "system", "content": system_prompt}]
    if req.history:
        messages.extend([{"role": h.role, "content": h.content} for h in req.history])
    messages.append({"role": "user", "content": req.message})

    # 3. Setup LLM Client
    # 豆包支持 plugin: web_search。如果是 search 模式，开启插件
    # 这里我们预留了 tools 的空间，或者直接使用 Doubao pro 模型自带的联网能力
    model_name = os.environ.get("DOUBAO_MODEL_ENDPOINT", "Doubao-Seed-2.0-lite-32k")
    
    ai_client = AsyncOpenAI(
        api_key=os.environ.get("NEW_API_KEY", ""),
        base_url="http://180.184.59.27:18887/v1" # Your Volcengine compatible proxy/endpoint
    )

    async def event_generator():
        try:
            # Prepare kwargs
            kwargs = {
                "model": model_name,
                "messages": messages,
                "stream": True,
                "temperature": 0.8 if req.mode == "roleplay" else 0.4
            }
            
            # If search mode, we might enable tools or specific model config if supported by Doubao
            # (Assuming the deployed model endpoint automatically handles web search or we pass a specific tool)
            # if req.mode == "search":
            #     kwargs["tools"] = [{"type": "web_search"}] 
            
            stream = await ai_client.chat.completions.create(**kwargs)
            
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield dict(data=json.dumps({"content": delta}))
            
            yield dict(data=json.dumps({"done": True}))
            
        except Exception as e:
            yield dict(data=json.dumps({"error": str(e)}))

    return EventSourceResponse(event_generator())
