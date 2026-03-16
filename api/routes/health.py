from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.schemas import HealthResponse
from api.services.queue import job_queue

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def healthz(db: AsyncSession = Depends(get_db)):
    db_status = "ok"
    redis_status = "ok"

    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    if not await job_queue.ping():
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthResponse(status=overall, database=db_status, redis=redis_status)
