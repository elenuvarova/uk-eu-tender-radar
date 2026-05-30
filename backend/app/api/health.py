from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import db_kind, engine

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": db_kind}
    except Exception as err:  # noqa: BLE001
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(err)}
        )


@router.get("/hello")
def hello():
    return {"message": "Hello from the backend 👋"}
