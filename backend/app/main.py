from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.opportunities import router as opp_router
from app.config import settings
from app.db import db_kind, init_db

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    print(f"Server starting (db: {db_kind})")
    yield


app = FastAPI(title="UK & EU Procurement Radar", lifespan=lifespan)
app.include_router(health_router)
app.include_router(opp_router)


if settings.is_production and PUBLIC_DIR.exists():
    # Serve built frontend; client-side routing falls back to index.html.
    if (PUBLIC_DIR / "assets").exists():
        app.mount(
            "/assets", StaticFiles(directory=PUBLIC_DIR / "assets"), name="assets"
        )

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        candidate = PUBLIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(PUBLIC_DIR / "index.html")
