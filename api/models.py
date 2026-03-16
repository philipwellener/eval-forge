import enum
import uuid

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.types import TypeDecorator, CHAR


class UUIDType(TypeDecorator):
    """Platform-independent UUID type. Uses CHAR(36) storage."""

    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value)
        return value


class Base(DeclarativeBase):
    pass


class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Policy(Base):
    __tablename__ = "policies"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    file_path = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    runs = relationship("EvaluationRun", back_populates="policy")


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUIDType, ForeignKey("policies.id"), nullable=False)
    environment = Column(String(100), nullable=False)
    num_runs = Column(Integer, nullable=False, default=10)
    config = Column(JSON, nullable=True)
    status = Column(Enum(RunStatus), nullable=False, default=RunStatus.PENDING)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    policy = relationship("Policy", back_populates="runs")
    results = relationship("EvaluationResult", back_populates="run")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    run_id = Column(UUIDType, ForeignKey("evaluation_runs.id"), nullable=False)
    episode_index = Column(Integer, nullable=False)
    success = Column(Integer, nullable=False)  # 0 or 1
    steps = Column(Integer, nullable=False)
    wall_clock_time = Column(Float, nullable=False)
    inference_latency = Column(Float, nullable=True)
    peak_memory_mb = Column(Float, nullable=True)
    extra_metadata = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    run = relationship("EvaluationRun", back_populates="results")
