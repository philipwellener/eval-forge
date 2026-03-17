import json
import os

import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_NAME = "eval_jobs"
CONSUMER_GROUP = "eval_workers"


class JobQueue:
    def __init__(self):
        self._redis: redis.Redis | None = None

    async def connect(self):
        self._redis = redis.from_url(REDIS_URL, decode_responses=True)
        try:
            await self._redis.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def close(self):
        if self._redis:
            await self._redis.aclose()

    async def publish(
        self,
        run_id: str,
        environment: str,
        policy_path: str,
        num_runs: int,
        config: dict | None = None,
    ):
        message = {
            "run_id": run_id,
            "environment": environment,
            "policy_path": policy_path,
            "num_runs": str(num_runs),
            "config": json.dumps(config or {}),
        }
        await self._redis.xadd(STREAM_NAME, message)

    async def consume(self, consumer_name: str, count: int = 1, block: int = 5000):
        messages = await self._redis.xreadgroup(
            CONSUMER_GROUP,
            consumer_name,
            {STREAM_NAME: ">"},
            count=count,
            block=block,
        )
        return messages

    async def ack(self, message_id: str):
        await self._redis.xack(STREAM_NAME, CONSUMER_GROUP, message_id)

    async def ping(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception:
            return False

    async def stream_length(self) -> int:
        try:
            return await self._redis.xlen(STREAM_NAME)
        except Exception:
            return 0


job_queue = JobQueue()
