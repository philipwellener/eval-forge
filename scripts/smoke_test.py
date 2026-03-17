"""End-to-end smoke test: upload policy → submit eval → poll → verify results."""

import os
import sys
import time

import httpx

API_URL = os.getenv("API_URL", "http://localhost:8000")
TIMEOUT = int(os.getenv("SMOKE_TIMEOUT", "120"))

# Inline random policy for upload
RANDOM_POLICY = """\
import numpy as np

class RandomPolicy:
    def __init__(self, action_dim):
        self.action_dim = action_dim

    def predict(self, observation):
        return np.random.uniform(-1.0, 1.0, size=self.action_dim)
"""


def main():
    client = httpx.Client(base_url=API_URL, timeout=30)

    # 1. Health check
    print("Checking API health...")
    resp = client.get("/healthz")
    assert resp.status_code == 200, f"Health check failed: {resp.text}"
    print(f"  Health: {resp.json()}")

    # 2. Upload policy
    print("Uploading random policy...")
    resp = client.post(
        "/api/v1/policies",
        params={"name": "smoke-test-random"},
        files={"file": ("random_policy.py", RANDOM_POLICY.encode(), "text/x-python")},
    )
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    policy_id = resp.json()["id"]
    print(f"  Policy ID: {policy_id}")

    # 3. Submit evaluation
    print("Submitting evaluation (reach, 5 runs)...")
    resp = client.post(
        "/api/v1/evaluations",
        json={
            "policy_id": policy_id,
            "environment": "reach",
            "num_runs": 5,
        },
    )
    assert resp.status_code == 201, f"Submit failed: {resp.text}"
    run_id = resp.json()["id"]
    print(f"  Run ID: {run_id}")

    # 4. Poll until complete
    print("Waiting for completion...")
    start = time.time()
    while time.time() - start < TIMEOUT:
        resp = client.get(f"/api/v1/evaluations/{run_id}")
        data = resp.json()
        status = data["status"]
        print(f"  Status: {status} ({time.time() - start:.0f}s elapsed)")

        if status == "completed":
            break
        elif status == "failed":
            print("FAILED: Evaluation failed")
            sys.exit(1)

        time.sleep(3)
    else:
        print(f"TIMEOUT: Evaluation did not complete within {TIMEOUT}s")
        sys.exit(1)

    # 5. Get results
    print("Fetching results...")
    resp = client.get(f"/api/v1/evaluations/{run_id}/results")
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 5, f"Expected 5 results, got {len(results)}"

    successes = sum(r["success"] for r in results)
    avg_time = sum(r["wall_clock_time"] for r in results) / len(results)
    avg_steps = sum(r["steps"] for r in results) / len(results)

    print("\n  Results summary:")
    print(f"    Episodes:    {len(results)}")
    print(f"    Successes:   {successes}/{len(results)} ({successes / len(results):.0%})")
    print(f"    Avg time:    {avg_time:.3f}s")
    print(f"    Avg steps:   {avg_steps:.0f}")

    for r in results:
        icon = "+" if r["success"] else "-"
        print(
            f"    [{icon}] Ep {r['episode_index']}: {r['steps']} steps, {r['wall_clock_time']:.3f}s"
        )

    print("\nSMOKE TEST PASSED")
    client.close()


if __name__ == "__main__":
    main()
