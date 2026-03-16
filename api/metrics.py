"""Prometheus metrics for EvalForge API."""
import time
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Counters
EVALS_SUBMITTED = Counter("evalforge_evals_submitted_total", "Total evaluations submitted", ["environment"])
EVALS_COMPLETED = Counter("evalforge_evals_completed_total", "Total evaluations completed", ["environment", "status"])
HTTP_REQUESTS = Counter("evalforge_http_requests_total", "Total HTTP requests", ["method", "path", "status"])

# Histograms
EVAL_DURATION = Histogram("evalforge_eval_duration_seconds", "Evaluation run duration", ["environment"],
                          buckets=[1, 5, 10, 30, 60, 120, 300, 600])
REQUEST_DURATION = Histogram("evalforge_request_duration_seconds", "HTTP request duration", ["method", "path"],
                             buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5])

# Gauges
ACTIVE_JOBS = Gauge("evalforge_active_jobs", "Currently active K8s jobs")
QUEUE_DEPTH = Gauge("evalforge_queue_depth", "Redis queue depth")


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        path = request.url.path
        # Normalize path to avoid high cardinality
        for prefix in ["/api/v1/policies/", "/api/v1/evaluations/"]:
            if path.startswith(prefix) and len(path) > len(prefix):
                path = prefix + "{id}"
                break

        REQUEST_DURATION.labels(method=request.method, path=path).observe(duration)
        HTTP_REQUESTS.labels(method=request.method, path=path, status=response.status_code).inc()
        return response


async def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
