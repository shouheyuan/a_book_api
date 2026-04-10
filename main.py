from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os

load_dotenv(override=True)

from app.routers import auth, profiles, reading, annotations, books, ai, billing, collections, lore

app = FastAPI(title="VisionNovel API", version="1.0", docs_url="/docs", redoc_url="/redoc")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.getenv("STATIC_DIR", "./static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

app.include_router(auth.router,        prefix="/v1/auth",             tags=["Auth"])
app.include_router(profiles.router,    prefix="/v1",                  tags=["Profiles"])
app.include_router(reading.router,     prefix="/v1/reading-sessions", tags=["Reading"])
app.include_router(annotations.router, prefix="/v1/annotations",      tags=["Annotations"])
app.include_router(books.router,       prefix="/v1",                  tags=["Books"])
app.include_router(ai.router,          prefix="/v1/ai",               tags=["AI"])
app.include_router(billing.router,     prefix="/v1/billing",          tags=["Billing"])
app.include_router(collections.router, prefix="/v1/collections",      tags=["Collections"])
app.include_router(lore.router,        prefix="/v1/lore-entities",    tags=["Lore"])

@app.get("/")
def root():
    return {"message": "VisionNovel API is running", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "ok"}
