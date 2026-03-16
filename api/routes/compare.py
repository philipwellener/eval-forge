from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import EvaluationResult, EvaluationRun
from api.schemas import CompareResponse, EvaluationRunResponse

router = APIRouter(prefix="/api/v1/compare", tags=["compare"])


@router.get("", response_model=CompareResponse)
async def compare_runs(
    run_ids: list[UUID] = Query(..., alias="run_id"),
    db: AsyncSession = Depends(get_db),
):
    if len(run_ids) < 2:
        raise HTTPException(status_code=400, detail="At least 2 run IDs required")

    runs = []
    results_map = {}

    for run_id in run_ids:
        result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        results_q = await db.execute(
            select(EvaluationResult)
            .where(EvaluationResult.run_id == run_id)
            .order_by(EvaluationResult.episode_index)
        )
        run_results = results_q.scalars().all()

        success_rate = None
        avg_time = None
        if run_results:
            success_rate = sum(r.success for r in run_results) / len(run_results)
            avg_time = sum(r.wall_clock_time for r in run_results) / len(run_results)

        runs.append(
            EvaluationRunResponse(
                id=run.id,
                policy_id=run.policy_id,
                environment=run.environment,
                num_runs=run.num_runs,
                config=run.config,
                status=run.status.value,
                submitted_at=run.submitted_at,
                started_at=run.started_at,
                completed_at=run.completed_at,
                success_rate=success_rate,
                avg_completion_time=avg_time,
            )
        )
        results_map[str(run_id)] = run_results

    return CompareResponse(runs=runs, results=results_map)
