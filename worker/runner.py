"""Worker that pulls jobs from Redis and runs PyBullet evaluations."""

import asyncio
import importlib.util
import json
import logging
import os
import signal
import sys
import time
import traceback
import uuid

import numpy as np
import psutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.services.queue import JobQueue  # noqa: E402
from worker.environments import ENV_REGISTRY  # noqa: E402
from worker.metrics import EPISODE_DURATION, EPISODES_TOTAL, MEMORY_RSS, push_metrics  # noqa: E402
from worker.reporting import ResultReporter  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("worker")

EVAL_TIMEOUT = int(os.getenv("EVAL_TIMEOUT", "60"))
ONE_SHOT = os.getenv("ONE_SHOT", "false").lower() == "true"


def load_policy_from_file(file_path: str, action_dim: int):
    """Dynamically load a policy class from a Python file."""
    spec = importlib.util.spec_from_file_location("policy_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Look for a class with a predict method
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and hasattr(attr, "predict") and attr_name != "object":
            return attr(action_dim=action_dim)

    raise ValueError(f"No policy class with predict() method found in {file_path}")


async def run_episode(env, policy, timeout: int = EVAL_TIMEOUT, config: dict | None = None) -> dict:
    """Run a single evaluation episode with timeout."""
    process = psutil.Process()
    start_mem = process.memory_info().rss / 1024 / 1024
    peak_mem = start_mem

    obs = env.reset(config=config)
    total_steps = 0
    inference_times = []
    start_time = time.time()

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                return {
                    "success": 0,
                    "steps": total_steps,
                    "wall_clock_time": elapsed,
                    "inference_latency": np.mean(inference_times) if inference_times else None,
                    "peak_memory_mb": peak_mem,
                    "metadata": {"timeout": True},
                }

            t0 = time.time()
            action = policy.predict(obs)
            inference_times.append(time.time() - t0)

            obs, reward, done, info = env.step(action)
            total_steps += 1

            current_mem = process.memory_info().rss / 1024 / 1024
            peak_mem = max(peak_mem, current_mem)

            if done:
                break

            # Yield control periodically
            if total_steps % 50 == 0:
                await asyncio.sleep(0)

    except Exception as e:
        return {
            "success": 0,
            "steps": total_steps,
            "wall_clock_time": time.time() - start_time,
            "inference_latency": np.mean(inference_times) if inference_times else None,
            "peak_memory_mb": peak_mem,
            "metadata": {"error": str(e), "traceback": traceback.format_exc()},
        }

    wall_time = time.time() - start_time
    success = int(env.get_success())
    EPISODE_DURATION.labels(environment="unknown").observe(wall_time)
    EPISODES_TOTAL.labels(environment="unknown", result="success" if success else "fail").inc()
    MEMORY_RSS.set(peak_mem)

    return {
        "success": success,
        "steps": total_steps,
        "wall_clock_time": wall_time,
        "inference_latency": np.mean(inference_times) if inference_times else None,
        "peak_memory_mb": peak_mem,
        "metadata": {},
    }


async def process_job(message_data: dict, reporter: ResultReporter):
    """Process a single evaluation job."""
    run_id = message_data["run_id"]
    environment = message_data["environment"]
    policy_path = message_data["policy_path"]
    num_runs = int(message_data["num_runs"])
    env_config = json.loads(message_data.get("config", "{}"))

    logger.info(f"Processing job: run_id={run_id}, env={environment}, num_runs={num_runs}")

    if environment not in ENV_REGISTRY:
        logger.error(f"Unknown environment: {environment}")
        await reporter.update_run_status(run_id, "failed")
        return

    env_cls = ENV_REGISTRY[environment]
    env = env_cls()

    try:
        policy = load_policy_from_file(policy_path, env.action_dim)
    except Exception as e:
        logger.error(f"Failed to load policy: {e}")
        await reporter.update_run_status(run_id, "failed")
        env.close()
        return

    await reporter.update_run_status(run_id, "running")

    for i in range(num_runs):
        logger.info(f"  Episode {i+1}/{num_runs} for run {run_id}")
        result = await run_episode(env, policy, config=env_config)

        await reporter.report_result(
            run_id=run_id,
            episode_index=i,
            success=result["success"],
            steps=result["steps"],
            wall_clock_time=result["wall_clock_time"],
            inference_latency=result["inference_latency"],
            peak_memory_mb=result["peak_memory_mb"],
            metadata=result["metadata"],
        )

    env.close()
    logger.info(f"Completed all episodes for run {run_id}")
    push_metrics(job_name=f"evalforge_worker_{run_id[:8]}")


async def main():
    consumer_name = f"worker-{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting worker: {consumer_name}")

    queue = JobQueue()
    await queue.connect()
    reporter = ResultReporter()

    shutdown = asyncio.Event()

    def handle_signal(*_):
        logger.info("Shutdown signal received")
        shutdown.set()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    try:
        while not shutdown.is_set():
            messages = await queue.consume(consumer_name, count=1, block=5000)

            if not messages:
                continue

            for stream_name, stream_messages in messages:
                for msg_id, msg_data in stream_messages:
                    try:
                        await process_job(msg_data, reporter)
                    except Exception as e:
                        logger.error(f"Job failed: {e}\n{traceback.format_exc()}")
                        try:
                            await reporter.update_run_status(msg_data["run_id"], "failed")
                        except Exception:
                            pass
                    finally:
                        await queue.ack(msg_id)

            if ONE_SHOT:
                break

    finally:
        await queue.close()
        await reporter.close()
        logger.info("Worker shut down")


if __name__ == "__main__":
    asyncio.run(main())
