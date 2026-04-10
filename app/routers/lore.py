import uuid, json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional, List
from app.db import get_db
from app.core.auth import get_current_user_id

router = APIRouter()

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class LoreEntityIn(BaseModel):
    id: Optional[str] = None          # client-side local id (int string) or cloud UUID
    book_id: str
    entity_type: str = "Character"    # Character | Item | Faction
    name: str
    aliases: Optional[str] = None
    appearance_desc: Optional[str] = None
    persona_desc: Optional[str] = None
    reference_image_url: Optional[str] = None
    history_images_json: Optional[str] = None  # JSON array of URLs

class LoreEntityOut(BaseModel):
    id: str
    book_id: str
    entity_type: str
    name: str
    aliases: Optional[str]
    appearance_desc: Optional[str]
    persona_desc: Optional[str]
    reference_image_url: Optional[str]
    history_images_json: Optional[str]
    created_at: str
    updated_at: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(r) -> dict:
    d = dict(r._mapping)
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    if d.get("updated_at"):
        d["updated_at"] = d["updated_at"].isoformat()
    return d

def _is_local_id(id_str: Optional[str]) -> bool:
    """Local GRDB IDs are small integers, cloud IDs are UUIDs."""
    if not id_str:
        return True
    try:
        int(id_str)
        return True
    except ValueError:
        return False

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/book/{book_id}", summary="获取书籍的所有角色档案")
def list_lore_entities(
    book_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text("SELECT * FROM lore_entities WHERE user_id=:uid AND book_id=:bid ORDER BY created_at DESC"),
        {"uid": user_id, "bid": book_id},
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


@router.post("", summary="新增或更新角色档案")
def upsert_lore_entity(
    payload: LoreEntityIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    # Determine cloud ID
    if payload.id and not _is_local_id(payload.id):
        cloud_id = payload.id  # already a UUID
    else:
        cloud_id = str(uuid.uuid4())  # assign new UUID

    existing = db.execute(
        text("SELECT id FROM lore_entities WHERE id=:id AND user_id=:uid"),
        {"id": cloud_id, "uid": user_id},
    ).fetchone()

    if existing:
        db.execute(
            text("""
                UPDATE lore_entities
                SET entity_type=:etype, name=:name, aliases=:aliases,
                    appearance_desc=:appearance, persona_desc=:persona,
                    reference_image_url=:ref_url, history_images_json=:hist
                WHERE id=:id AND user_id=:uid
            """),
            {
                "etype": payload.entity_type,
                "name": payload.name,
                "aliases": payload.aliases,
                "appearance": payload.appearance_desc,
                "persona": payload.persona_desc,
                "ref_url": payload.reference_image_url,
                "hist": payload.history_images_json,
                "id": cloud_id,
                "uid": user_id,
            },
        )
    else:
        db.execute(
            text("""
                INSERT INTO lore_entities
                  (id, user_id, book_id, entity_type, name, aliases,
                   appearance_desc, persona_desc, reference_image_url, history_images_json)
                VALUES
                  (:id, :uid, :bid, :etype, :name, :aliases,
                   :appearance, :persona, :ref_url, :hist)
            """),
            {
                "id": cloud_id,
                "uid": user_id,
                "bid": payload.book_id,
                "etype": payload.entity_type,
                "name": payload.name,
                "aliases": payload.aliases,
                "appearance": payload.appearance_desc,
                "persona": payload.persona_desc,
                "ref_url": payload.reference_image_url,
                "hist": payload.history_images_json,
            },
        )

    db.commit()
    row = db.execute(
        text("SELECT * FROM lore_entities WHERE id=:id"), {"id": cloud_id}
    ).fetchone()
    return _row_to_dict(row)


@router.put("/{entity_id}", summary="更新角色档案")
def update_lore_entity(
    entity_id: str,
    payload: LoreEntityIn,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    db.execute(
        text("""
            UPDATE lore_entities
            SET entity_type=:etype, name=:name, aliases=:aliases,
                appearance_desc=:appearance, persona_desc=:persona,
                reference_image_url=:ref_url, history_images_json=:hist
            WHERE id=:id AND user_id=:uid
        """),
        {
            "etype": payload.entity_type,
            "name": payload.name,
            "aliases": payload.aliases,
            "appearance": payload.appearance_desc,
            "persona": payload.persona_desc,
            "ref_url": payload.reference_image_url,
            "hist": payload.history_images_json,
            "id": entity_id,
            "uid": user_id,
        },
    )
    db.commit()
    row = db.execute(
        text("SELECT * FROM lore_entities WHERE id=:id"), {"id": entity_id}
    ).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Not found")
    return _row_to_dict(row)


@router.delete("/{entity_id}", summary="删除角色档案")
def delete_lore_entity(
    entity_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    db.execute(
        text("DELETE FROM lore_entities WHERE id=:id AND user_id=:uid"),
        {"id": entity_id, "uid": user_id},
    )
    db.commit()
    return {"message": "deleted"}


@router.post("/batch-sync", summary="批量同步（iOS 推送本地全量）")
def batch_sync(
    entities: List[LoreEntityIn],
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    results = []
    for payload in entities:
        if payload.id and not _is_local_id(payload.id):
            cloud_id = payload.id
        else:
            cloud_id = str(uuid.uuid4())

        existing = db.execute(
            text("SELECT id FROM lore_entities WHERE id=:id"), {"id": cloud_id}
        ).fetchone()

        if existing:
            db.execute(
                text("""
                    UPDATE lore_entities
                    SET entity_type=:etype, name=:name, aliases=:aliases,
                        appearance_desc=:appearance, persona_desc=:persona,
                        reference_image_url=:ref_url, history_images_json=:hist
                    WHERE id=:id AND user_id=:uid
                """),
                {
                    "etype": payload.entity_type, "name": payload.name,
                    "aliases": payload.aliases, "appearance": payload.appearance_desc,
                    "persona": payload.persona_desc, "ref_url": payload.reference_image_url,
                    "hist": payload.history_images_json, "id": cloud_id, "uid": user_id,
                },
            )
        else:
            db.execute(
                text("""
                    INSERT INTO lore_entities
                      (id, user_id, book_id, entity_type, name, aliases,
                       appearance_desc, persona_desc, reference_image_url, history_images_json)
                    VALUES (:id,:uid,:bid,:etype,:name,:aliases,:appearance,:persona,:ref_url,:hist)
                """),
                {
                    "id": cloud_id, "uid": user_id, "bid": payload.book_id,
                    "etype": payload.entity_type, "name": payload.name,
                    "aliases": payload.aliases, "appearance": payload.appearance_desc,
                    "persona": payload.persona_desc, "ref_url": payload.reference_image_url,
                    "hist": payload.history_images_json,
                },
            )
        results.append(cloud_id)

    db.commit()
    return {"synced": len(results), "ids": results}
