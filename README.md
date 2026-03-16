# EvalForge

Self-hosted robot policy evaluation platform. Submit trained policies, run parallel PyBullet simulations across Kubernetes, and compare results through a web dashboard.

ML engineers submit policy files through the API or CLI, and EvalForge orchestrates headless PyBullet simulations across worker pods. Each policy is evaluated against three robotic manipulation tasks of increasing difficulty — from simple reaching to cluttered pick-and-place with obstacle avoidance. Per-episode telemetry (success rate, completion time, inference latency, memory usage) is stored in Postgres and surfaced through a React dashboard with real-time status polling, detailed run breakdowns, and side-by-side policy comparison charts. The system is designed for self-hosted deployment on Kubernetes with Prometheus/Grafana observability, TLS termination, and rate limiting out of the box.

## Screenshots

<!-- Replace with your own screenshots -->

![Runs List](docs/screenshots/runs-list.png)
*Evaluation runs with live status, success rates, and environment filtering.*

![Compare View](docs/screenshots/compare-view.png)
*Side-by-side policy comparison with per-metric charts and winner highlighting.*

## Architecture

```
┌─────────────┐     ┌───────────┐     ┌─────────────┐
│  Dashboard   │────▶│   Nginx   │────▶│  FastAPI     │
│  (React)     │     │  (TLS)    │     │  API Server  │
└─────────────┘     └───────────┘     └──────┬───────┘
                                             │
                              ┌──────────────┼──────────────┐
                              ▼              ▼              ▼
                        ┌──────────┐  ┌──────────┐  ┌────────────┐
                        │ Postgres │  │  Redis   │  │ K8s Jobs   │
                        │  (data)  │  │ (queue)  │  │ (workers)  │
                        └──────────┘  └──────────┘  └────────────┘
                                                         │
                                                    ┌────┴────┐
                                                    │ PyBullet│
                                                    │  Sims   │
                                                    └─────────┘
```

## Quick Start

### Local Development (Docker Compose)

```bash
# Start all services (API + Postgres + Redis + 4 workers)
make dev

# Run smoke test
python scripts/smoke_test.py
```

### Kubernetes (kind)

```bash
# Create cluster, build images, deploy everything
make k8s-up

# Tear down
make k8s-down
```

### CLI

```bash
# Install
uv pip install -e .

# Submit an evaluation
evalforge submit --policy examples/random_policy.py --name my-policy --environment reach --num-runs 20 --wait

# Check status
evalforge status <run-id>

# View results
evalforge results <run-id>

# List runs
evalforge list

# Compare runs
evalforge compare <run-id-1> <run-id-2>
```

## Environments

| Environment | Description | Max Steps | Difficulty |
|-------------|-------------|-----------|------------|
| `reach` | Panda arm reaches target point | 200 | Easy |
| `pick_place` | Pick cube, place at target | 500 | Medium |
| `cluttered` | Pick with obstacles, collision tracking | 500 | Hard |

## Metrics Collected

- **Success/Failure** per episode
- **Steps** to completion
- **Wall clock time** per episode
- **Inference latency** (policy forward pass)
- **Peak RSS memory** usage
- **Collision count** (cluttered environment)

## Observability

- **Prometheus** scrapes API metrics at `/metrics`
- **Grafana** dashboards at `localhost:3000`:
  - System Overview
  - Evaluation Performance
  - Resource Utilization
  - SLIs

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://evalforge:evalforge@localhost:5432/evalforge` | Postgres connection |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `UPLOAD_DIR` | `/tmp/evalforge/policies` | Policy file storage |
| `API_URL` | `http://localhost:8000` | API URL (for workers) |
| `EVALFORGE_API_URL` | `http://localhost:8000` | API URL (for CLI) |
| `MAX_CONCURRENT_JOBS` | `10` | K8s job concurrency limit |
| `EVAL_TIMEOUT` | `60` | Per-episode timeout (seconds) |
| `ONE_SHOT` | `false` | Worker exits after one job |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI, SQLAlchemy (async), Pydantic |
| Database | PostgreSQL 16 |
| Queue | Redis 7 (Streams) |
| Simulation | PyBullet (DIRECT mode) |
| Orchestration | Kubernetes (kind for dev) |
| Proxy | Nginx (TLS, rate limiting) |
| Monitoring | Prometheus + Grafana |
| Dashboard | React, TypeScript, Recharts, Tailwind |
| CLI | Click |
| CI | GitHub Actions |
| Package Manager | uv |

## Development

```bash
# Install dev dependencies
uv sync --extra dev --extra worker

# Run tests
make test

# Lint
make lint

# Format
make format
```
