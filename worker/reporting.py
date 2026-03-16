import os

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000")


class ResultReporter:
    def __init__(self):
        self._client = httpx.AsyncClient(base_url=API_URL, timeout=30)

    async def report_result(
        self,
        run_id: str,
        episode_index: int,
        success: int,
        steps: int,
        wall_clock_time: float,
        inference_latency: float | None = None,
        peak_memory_mb: float | None = None,
        metadata: dict | None = None,
    ):
        payload = {
            "run_id": run_id,
            "episode_index": episode_index,
            "success": success,
            "steps": steps,
            "wall_clock_time": wall_clock_time,
            "inference_latency": inference_latency,
            "peak_memory_mb": peak_memory_mb,
            "extra_metadata": metadata,
        }
        resp = await self._client.post("/api/v1/evaluations/results", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def update_run_status(self, run_id: str, status: str):
        resp = await self._client.patch(
            f"/api/v1/evaluations/{run_id}/status",
            params={"status": status},
        )
        resp.raise_for_status()

    async def get_run(self, run_id: str) -> dict:
        resp = await self._client.get(f"/api/v1/evaluations/{run_id}")
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self._client.aclose()
