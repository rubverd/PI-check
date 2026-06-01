from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.infrastructure.database.session import get_db_session
from app.infrastructure.external.mobsf_client import check_mobsf_health


router = APIRouter(
    prefix="/api/system",
    tags=["system"],
)


@router.get("/db-health")
def db_health(db: Session = Depends(get_db_session)):
    result = db.execute(text("SELECT 1")).scalar_one()

    return {
        "database": "ok",
        "result": result,
    }


@router.get("/mobsf-health")
def mobsf_health():
    return check_mobsf_health()