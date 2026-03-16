"""EvalForge CLI — submit and monitor robot policy evaluations."""

import os
import sys
import time

import click
import httpx

API_URL = os.getenv("EVALFORGE_API_URL", "http://localhost:8000")


def get_client():
    return httpx.Client(base_url=API_URL, timeout=30)


@click.group()
@click.option("--api-url", envvar="EVALFORGE_API_URL", default=API_URL, help="API base URL")
@click.pass_context
def cli(ctx, api_url):
    """EvalForge — Robot Policy Evaluation Platform"""
    ctx.ensure_object(dict)
    ctx.obj["api_url"] = api_url


@cli.command()
@click.option("--policy", required=True, type=click.Path(exists=True), help="Path to policy file")
@click.option("--name", required=True, help="Policy name")
@click.option("--environment", required=True, type=click.Choice(["reach", "pick_place", "cluttered"]))
@click.option("--num-runs", default=10, help="Number of evaluation episodes")
@click.option("--wait", is_flag=True, help="Wait for completion")
@click.pass_context
def submit(ctx, policy, name, environment, num_runs, wait):
    """Submit a policy for evaluation."""
    client = httpx.Client(base_url=ctx.obj["api_url"], timeout=30)

    # Upload policy
    click.echo(f"Uploading policy '{name}'...")
    with open(policy, "rb") as f:
        resp = client.post(
            "/api/v1/policies",
            params={"name": name},
            files={"file": (os.path.basename(policy), f, "text/x-python")},
        )
    resp.raise_for_status()
    policy_data = resp.json()
    policy_id = policy_data["id"]
    click.echo(f"  Policy ID: {policy_id}")

    # Submit evaluation
    click.echo(f"Submitting evaluation: {environment} x {num_runs} runs...")
    resp = client.post(
        "/api/v1/evaluations",
        json={
            "policy_id": policy_id,
            "environment": environment,
            "num_runs": num_runs,
        },
    )
    resp.raise_for_status()
    run_data = resp.json()
    run_id = run_data["id"]
    click.echo(f"  Run ID: {run_id}")

    if wait:
        click.echo("Waiting for completion...")
        while True:
            resp = client.get(f"/api/v1/evaluations/{run_id}")
            status = resp.json()["status"]
            click.echo(f"  Status: {status}", nl=False)
            click.echo("\r", nl=False)
            if status in ("completed", "failed"):
                click.echo(f"\n  Final status: {status}")
                break
            time.sleep(2)

        # Print summary
        resp = client.get(f"/api/v1/evaluations/{run_id}")
        data = resp.json()
        if data.get("success_rate") is not None:
            click.echo(f"  Success rate: {data['success_rate']:.1%}")
        if data.get("avg_completion_time") is not None:
            click.echo(f"  Avg completion time: {data['avg_completion_time']:.3f}s")

    client.close()


@cli.command()
@click.argument("run_id")
@click.pass_context
def status(ctx, run_id):
    """Check evaluation run status."""
    client = httpx.Client(base_url=ctx.obj["api_url"], timeout=30)
    resp = client.get(f"/api/v1/evaluations/{run_id}")
    resp.raise_for_status()
    data = resp.json()

    click.echo(f"Run ID:      {data['id']}")
    click.echo(f"Environment: {data['environment']}")
    click.echo(f"Status:      {data['status']}")
    click.echo(f"Num runs:    {data['num_runs']}")
    if data.get("success_rate") is not None:
        click.echo(f"Success:     {data['success_rate']:.1%}")
    client.close()


@cli.command()
@click.argument("run_id")
@click.pass_context
def results(ctx, run_id):
    """Get detailed results for an evaluation run."""
    client = httpx.Client(base_url=ctx.obj["api_url"], timeout=30)
    resp = client.get(f"/api/v1/evaluations/{run_id}/results")
    resp.raise_for_status()
    data = resp.json()

    for r in data:
        status_icon = "+" if r["success"] else "-"
        click.echo(
            f"  [{status_icon}] Episode {r['episode_index']:3d}: "
            f"steps={r['steps']:4d}  time={r['wall_clock_time']:.3f}s  "
            f"latency={r.get('inference_latency', 0) or 0:.4f}s  "
            f"mem={r.get('peak_memory_mb', 0) or 0:.1f}MB"
        )
    client.close()


@cli.command("list")
@click.option("--environment", type=click.Choice(["reach", "pick_place", "cluttered"]))
@click.option("--status", "run_status", type=click.Choice(["pending", "running", "completed", "failed"]))
@click.pass_context
def list_runs(ctx, environment, run_status):
    """List evaluation runs."""
    client = httpx.Client(base_url=ctx.obj["api_url"], timeout=30)
    params = {}
    if environment:
        params["environment"] = environment
    if run_status:
        params["status"] = run_status

    resp = client.get("/api/v1/evaluations", params=params)
    resp.raise_for_status()
    runs = resp.json()

    if not runs:
        click.echo("No evaluation runs found.")
        return

    click.echo(f"{'ID':36s}  {'Environment':12s}  {'Status':10s}  {'Runs':5s}  {'Success':8s}")
    click.echo("-" * 80)
    for run in runs:
        sr = f"{run['success_rate']:.0%}" if run.get("success_rate") is not None else "—"
        click.echo(
            f"{run['id']:36s}  {run['environment']:12s}  {run['status']:10s}  "
            f"{run['num_runs']:5d}  {sr:>8s}"
        )
    client.close()


@cli.command()
@click.argument("run_ids", nargs=-1, required=True)
@click.pass_context
def compare(ctx, run_ids):
    """Compare multiple evaluation runs."""
    if len(run_ids) < 2:
        click.echo("Error: At least 2 run IDs required.", err=True)
        sys.exit(1)

    client = httpx.Client(base_url=ctx.obj["api_url"], timeout=30)
    params = [("run_id", rid) for rid in run_ids]
    resp = client.get("/api/v1/compare", params=params)
    resp.raise_for_status()
    data = resp.json()

    click.echo(f"\n{'Policy ID':36s}  {'Environment':12s}  {'Success':8s}  {'Avg Time':10s}")
    click.echo("-" * 72)
    for run in data["runs"]:
        sr = f"{run['success_rate']:.0%}" if run.get("success_rate") is not None else "—"
        at = f"{run['avg_completion_time']:.3f}s" if run.get("avg_completion_time") is not None else "—"
        click.echo(f"{run['policy_id']:36s}  {run['environment']:12s}  {sr:>8s}  {at:>10s}")

    client.close()


if __name__ == "__main__":
    cli()
