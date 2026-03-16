import io

import pytest


@pytest.mark.asyncio
async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert data["redis"] == "ok"


@pytest.mark.asyncio
async def test_upload_policy(client):
    file_content = b"class TestPolicy:\n    def __init__(self, action_dim):\n        pass\n    def predict(self, obs):\n        return [0.0]\n"
    resp = await client.post(
        "/api/v1/policies",
        params={"name": "test-policy", "description": "A test policy"},
        files={"file": ("test_policy.py", io.BytesIO(file_content), "text/x-python")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-policy"
    assert data["description"] == "A test policy"
    assert "id" in data
    return data["id"]


@pytest.mark.asyncio
async def test_list_policies(client):
    # Upload first
    file_content = b"class P:\n    def __init__(self, action_dim): pass\n    def predict(self, obs): return [0]\n"
    await client.post(
        "/api/v1/policies",
        params={"name": "list-test"},
        files={"file": ("p.py", io.BytesIO(file_content), "text/x-python")},
    )

    resp = await client.get("/api/v1/policies")
    assert resp.status_code == 200
    policies = resp.json()
    assert len(policies) >= 1


@pytest.mark.asyncio
async def test_submit_evaluation(client, mock_queue):
    # Upload policy
    file_content = b"class P:\n    def __init__(self, action_dim): pass\n    def predict(self, obs): return [0]\n"
    policy_resp = await client.post(
        "/api/v1/policies",
        params={"name": "eval-test"},
        files={"file": ("p.py", io.BytesIO(file_content), "text/x-python")},
    )
    policy_id = policy_resp.json()["id"]

    # Submit evaluation
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "policy_id": policy_id,
            "environment": "reach",
            "num_runs": 5,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending"
    assert data["environment"] == "reach"
    assert data["num_runs"] == 5

    # Verify Redis publish was called
    mock_queue.publish.assert_called_once()


@pytest.mark.asyncio
async def test_list_evaluations(client):
    resp = await client.get("/api/v1/evaluations")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_submit_eval_invalid_policy(client):
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "policy_id": "00000000-0000-0000-0000-000000000000",
            "environment": "reach",
            "num_runs": 5,
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_eval_invalid_environment(client):
    resp = await client.post(
        "/api/v1/evaluations",
        json={
            "policy_id": "00000000-0000-0000-0000-000000000000",
            "environment": "invalid_env",
            "num_runs": 5,
        },
    )
    assert resp.status_code == 422
