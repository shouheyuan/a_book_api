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
