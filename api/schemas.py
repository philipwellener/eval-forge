from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None


class PolicyResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    file_path: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationSubmit(BaseModel):
    policy_id: UUID
    environment: str = Field(..., pattern=r"^(reach|pick_place|cluttered)$")
    num_runs: int = Field(default=10, ge=1, le=1000)
    config: dict | None = None


class EvaluationRunResponse(BaseModel):
    id: UUID
    policy_id: UUID
    environment: str
    num_runs: int
    config: dict | None
    status: str
    submitted_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    success_rate: float | None = None
    avg_completion_time: float | None = None

    model_config = {"from_attributes": True}


class EvaluationResultCreate(BaseModel):
    run_id: UUID
    episode_index: int
    success: int = Field(..., ge=0, le=1)
    steps: int = Field(..., ge=0)
    wall_clock_time: float = Field(..., ge=0)
    inference_latency: float | None = None
    peak_memory_mb: float | None = None
    extra_metadata: dict | None = None


class EvaluationResultResponse(BaseModel):
    id: UUID
    run_id: UUID
    episode_index: int
    success: int
    steps: int
    wall_clock_time: float
    inference_latency: float | None
    peak_memory_mb: float | None
    extra_metadata: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CompareResponse(BaseModel):
    runs: list[EvaluationRunResponse]
    results: dict[str, list[EvaluationResultResponse]]


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
