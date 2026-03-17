"""Kubernetes Job orchestrator for evaluation runs."""

import asyncio
import logging
import os
from kubernetes_asyncio import client, config
from kubernetes_asyncio.client import ApiException

logger = logging.getLogger("orchestrator")

NAMESPACE = os.getenv("K8S_NAMESPACE", "evalforge")
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "10"))
WORKER_IMAGE = os.getenv("WORKER_IMAGE", "evalforge-worker:latest")


class JobOrchestrator:
    def __init__(self):
        self._batch_api = None
        self._core_api = None
        self._running = False

    async def start(self):
        try:
            config.load_incluster_config()
        except config.ConfigException:
            await config.load_kube_config()
        self._batch_api = client.BatchV1Api()
        self._core_api = client.CoreV1Api()
        self._running = True
        logger.info("Job orchestrator started")

    async def stop(self):
        self._running = False
        await client.ApiClient().close()

    async def create_job(
        self,
        run_id: str,
        environment: str,
        policy_path: str,
        num_runs: int,
        run_config: dict | None = None,
    ):
        active = await self.get_active_job_count()
        if active >= MAX_CONCURRENT_JOBS:
            logger.warning(
                f"Concurrency limit reached ({active}/{MAX_CONCURRENT_JOBS}), queuing job"
            )
            return None

        job_name = f"eval-{run_id[:8]}"
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        api_url = os.getenv("API_INTERNAL_URL", "http://evalforge-api:8000")

        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(
                name=job_name,
                namespace=NAMESPACE,
                labels={"app": "evalforge-worker", "run-id": run_id[:63]},
            ),
            spec=client.V1JobSpec(
                backoff_limit=1,
                ttl_seconds_after_finished=300,
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(
                        labels={"app": "evalforge-worker", "run-id": run_id[:63]},
                    ),
                    spec=client.V1PodSpec(
                        restart_policy="Never",
                        containers=[
                            client.V1Container(
                                name="worker",
                                image=WORKER_IMAGE,
                                image_pull_policy="Never",
                                env=[
                                    client.V1EnvVar(name="REDIS_URL", value=redis_url),
                                    client.V1EnvVar(name="API_URL", value=api_url),
                                    client.V1EnvVar(name="ONE_SHOT", value="true"),
                                ],
                                resources=client.V1ResourceRequirements(
                                    requests={"memory": "256Mi", "cpu": "250m"},
                                    limits={"memory": "512Mi", "cpu": "500m"},
                                ),
                            )
                        ],
                    ),
                ),
            ),
        )

        try:
            result = await self._batch_api.create_namespaced_job(namespace=NAMESPACE, body=job)
            logger.info(f"Created job {job_name} for run {run_id}")
            return result
        except ApiException as e:
            logger.error(f"Failed to create job: {e}")
            raise

    async def get_active_job_count(self) -> int:
        try:
            jobs = await self._batch_api.list_namespaced_job(
                namespace=NAMESPACE,
                label_selector="app=evalforge-worker",
            )
            active = sum(1 for j in jobs.items if j.status.active)
            return active
        except Exception:
            return 0

    async def get_job_counts(self) -> dict:
        try:
            jobs = await self._batch_api.list_namespaced_job(
                namespace=NAMESPACE,
                label_selector="app=evalforge-worker",
            )
            counts = {"active": 0, "succeeded": 0, "failed": 0}
            for j in jobs.items:
                if j.status.active:
                    counts["active"] += j.status.active or 0
                counts["succeeded"] += j.status.succeeded or 0
                counts["failed"] += j.status.failed or 0
            return counts
        except Exception:
            return {"active": 0, "succeeded": 0, "failed": 0, "error": "unavailable"}

    async def watch_jobs(self, db_session_factory):
        """Background task to watch for completed/failed jobs and update DB."""
        from api.models import EvaluationRun, RunStatus
        from sqlalchemy import select

        while self._running:
            try:
                jobs = await self._batch_api.list_namespaced_job(
                    namespace=NAMESPACE,
                    label_selector="app=evalforge-worker",
                )
                for job in jobs.items:
                    run_id = job.metadata.labels.get("run-id")
                    if not run_id:
                        continue

                    if job.status.failed and job.status.failed > 0:
                        async with db_session_factory() as session:
                            result = await session.execute(
                                select(EvaluationRun).where(
                                    EvaluationRun.id == run_id,
                                    EvaluationRun.status.in_(
                                        [RunStatus.PENDING, RunStatus.RUNNING]
                                    ),
                                )
                            )
                            run = result.scalar_one_or_none()
                            if run:
                                run.status = RunStatus.FAILED
                                await session.commit()
                                logger.info(f"Marked run {run_id} as failed (job failed)")

            except Exception as e:
                logger.error(f"Job watcher error: {e}")

            await asyncio.sleep(10)


orchestrator = JobOrchestrator()
