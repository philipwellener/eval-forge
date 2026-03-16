from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.database import engine
from api.metrics import MetricsMiddleware, metrics_endpoint
from api.models import Base
from api.routes import compare, evaluations, health, policies
from api.services.queue import job_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await job_queue.connect()
    yield
    # Shutdown
    await job_queue.close()
    await engine.dispose()


app = FastAPI(title="EvalForge", version="0.1.0", lifespan=lifespan)

app.add_middleware(MetricsMiddleware)

app.include_router(health.router)
app.include_router(policies.router)
app.include_router(evaluations.router)
app.include_router(compare.router)

app.get("/metrics")(metrics_endpoint)
