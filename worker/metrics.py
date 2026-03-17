"""Prometheus metrics for EvalForge workers (push to Pushgateway)."""

import os
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    push_to_gateway,
)

PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "localhost:9091")
WORKER_REGISTRY = CollectorRegistry()

EPISODES_TOTAL = Counter(
    "evalforge_worker_episodes_total",
    "Episodes run by worker",
    ["environment", "result"],
    registry=WORKER_REGISTRY,
)
EPISODE_DURATION = Histogram(
    "evalforge_worker_episode_duration_seconds",
    "Episode wall clock time",
    ["environment"],
    buckets=[0.5, 1, 2, 5, 10, 30, 60],
    registry=WORKER_REGISTRY,
)
SIM_STEP_DURATION = Histogram(
    "evalforge_worker_sim_step_seconds",
    "Simulation step duration",
    ["environment"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01],
    registry=WORKER_REGISTRY,
)
INFERENCE_DURATION = Histogram(
    "evalforge_worker_inference_seconds",
    "Policy inference duration",
    ["environment"],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05],
    registry=WORKER_REGISTRY,
)
WORKER_ERRORS = Counter(
    "evalforge_worker_errors_total",
    "Worker errors",
    ["environment", "error_type"],
    registry=WORKER_REGISTRY,
)
MEMORY_RSS = Gauge(
    "evalforge_worker_memory_rss_mb",
    "Worker RSS memory in MB",
    registry=WORKER_REGISTRY,
)


def push_metrics(job_name: str = "evalforge_worker"):
    try:
        push_to_gateway(PUSHGATEWAY_URL, job=job_name, registry=WORKER_REGISTRY)
    except Exception:
        pass  # Best effort
