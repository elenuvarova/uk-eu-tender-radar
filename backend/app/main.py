from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.opportunities import router as opp_router
from app.api.profile import router as profile_router
from app.api.buyers import router as buyers_router
from app.config import settings
from app.db import db_kind, init_db

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema ownership: Postgres (prod) is migrated solely by `alembic upgrade
    # head` in the Docker CMD. Only the SQLite/local/test path creates tables
    # here, so we never have two schema owners racing on the same database.
    if db_kind == "sqlite":
        init_db()
    print(f"Server starting (db: {db_kind})")
    yield


app = FastAPI(title="UK & EU Procurement Radar", lifespan=lifespan)

# CORS. allow_origins is an explicit allow-list (never "*") so credentialed
# requests stay safe; empty list in prod since the SPA is served same-origin.
if settings.allowed_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

app.include_router(health_router)
app.include_router(opp_router)
app.include_router(profile_router)
app.include_router(buyers_router)


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
