import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import db_kind, engine

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": db_kind}
    except Exception:  # noqa: BLE001
        # Log the full exception server-side; never leak DB/driver internals
        # (connection strings, host names) to the client.
        log.exception("Health check DB probe failed")
        return JSONResponse(status_code=500, content={"status": "error"})


@router.get("/hello")
def hello():
    return {"message": "Hello from the backend 👋"}
