import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import EvaluationResult, EvaluationRun, Policy, RunStatus
from api.schemas import (
    EvaluationResultCreate,
    EvaluationResultResponse,
    EvaluationRunResponse,
    EvaluationSubmit,
)
from api.services.queue import job_queue

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


def _run_to_response(run: EvaluationRun, results: list[EvaluationResult] | None = None) -> dict:
    data = {
        "id": run.id,
        "policy_id": run.policy_id,
        "environment": run.environment,
        "num_runs": run.num_runs,
        "config": run.config,
        "status": run.status.value if isinstance(run.status, RunStatus) else run.status,
        "submitted_at": run.submitted_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }
    if results:
        successes = sum(r.success for r in results)
        data["success_rate"] = successes / len(results) if results else None
        data["avg_completion_time"] = (
            sum(r.wall_clock_time for r in results) / len(results) if results else None
        )
    return data


@router.post("", response_model=EvaluationRunResponse, status_code=201)
async def submit_evaluation(body: EvaluationSubmit, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Policy).where(Policy.id == body.policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    run = EvaluationRun(
        policy_id=body.policy_id,
        environment=body.environment,
        num_runs=body.num_runs,
        config=body.config,
        status=RunStatus.PENDING,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    await job_queue.publish(
        run_id=str(run.id),
        environment=body.environment,
        policy_path=policy.file_path,
        num_runs=body.num_runs,
        config=body.config,
    )

    return _run_to_response(run)


@router.get("", response_model=list[EvaluationRunResponse])
async def list_evaluations(
    environment: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(EvaluationRun).order_by(EvaluationRun.submitted_at.desc())
    if environment:
        query = query.where(EvaluationRun.environment == environment)
    if status:
        query = query.where(EvaluationRun.status == status)
    result = await db.execute(query)
    runs = result.scalars().all()

    responses = []
    for r in runs:
        results_q = await db.execute(
            select(EvaluationResult).where(EvaluationResult.run_id == r.id)
        )
        run_results = results_q.scalars().all()
        responses.append(_run_to_response(r, run_results if run_results else None))
    return responses


@router.get("/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")

    results_q = await db.execute(select(EvaluationResult).where(EvaluationResult.run_id == run_id))
    results = results_q.scalars().all()
    return _run_to_response(run, results)


@router.get("/{run_id}/results", response_model=list[EvaluationResultResponse])
async def get_results(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Evaluation run not found")

    results_q = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.run_id == run_id)
        .order_by(EvaluationResult.episode_index)
    )
    return results_q.scalars().all()


@router.post("/results", response_model=EvaluationResultResponse, status_code=201)
async def create_result(body: EvaluationResultCreate, db: AsyncSession = Depends(get_db)):
    result_obj = await db.execute(select(EvaluationRun).where(EvaluationRun.id == body.run_id))
    run = result_obj.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")

    if run.status == RunStatus.PENDING:
        run.status = RunStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)

    eval_result = EvaluationResult(**body.model_dump())
    db.add(eval_result)

    # Check if all results are in
    existing = await db.execute(
        select(EvaluationResult).where(EvaluationResult.run_id == body.run_id)
    )
    count = len(existing.scalars().all()) + 1  # +1 for the one we're adding
    if count >= run.num_runs:
        run.status = RunStatus.COMPLETED
        run.completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(eval_result)
    return eval_result


@router.patch("/{run_id}/status")
async def update_run_status(
    run_id: uuid.UUID,
    status: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Evaluation run not found")

    run.status = RunStatus(status)
    if status == "running" and not run.started_at:
        run.started_at = datetime.now(timezone.utc)
    elif status in ("completed", "failed"):
        run.completed_at = datetime.now(timezone.utc)

    await db.commit()
    return {"status": run.status.value}
