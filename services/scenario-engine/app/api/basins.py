from unittest import result
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from sqlalchemy import text

router = APIRouter(prefix="/basins", tags=["basins"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def list_basins(db: Session = Depends(get_db)):
    result = db.execute(text("select * from basins"))
    rows = result.mappings().all()
    return rows


