.PHONY: dev migrate test lint k8s-up k8s-down

dev:
	docker compose up --build

migrate:
	uv run alembic upgrade head

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

k8s-up:
	bash scripts/k8s_setup.sh

k8s-down:
	kind delete cluster --name evalforge
