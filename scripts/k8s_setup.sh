#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="evalforge"

echo "=== EvalForge K8s Setup ==="

# 1. Create kind cluster
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Cluster '${CLUSTER_NAME}' already exists"
else
    echo "Creating kind cluster..."
    cat <<EOF | kind create cluster --name "${CLUSTER_NAME}" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
  - role: control-plane
    extraPortMappings:
      - containerPort: 30080
        hostPort: 80
      - containerPort: 30443
        hostPort: 443
      - containerPort: 30300
        hostPort: 3000
EOF
fi

# 2. Build Docker images
echo "Building Docker images..."
docker build -t evalforge-api:latest -f infra/docker/Dockerfile.api .
docker build -t evalforge-worker:latest -f infra/docker/Dockerfile.worker .

if [ -f infra/docker/Dockerfile.dashboard ] && [ -d dashboard/node_modules ]; then
    docker build -t evalforge-dashboard:latest -f infra/docker/Dockerfile.dashboard .
fi

# 3. Load images into kind
echo "Loading images into kind..."
kind load docker-image evalforge-api:latest --name "${CLUSTER_NAME}"
kind load docker-image evalforge-worker:latest --name "${CLUSTER_NAME}"

# 4. Apply manifests
echo "Applying Kubernetes manifests..."
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/postgres-statefulset.yaml
kubectl apply -f infra/k8s/redis-deployment.yaml

echo "Waiting for Postgres and Redis..."
kubectl -n evalforge wait --for=condition=ready pod -l app=postgres --timeout=120s
kubectl -n evalforge wait --for=condition=ready pod -l app=redis --timeout=60s

kubectl apply -f infra/k8s/api-deployment.yaml

echo "Waiting for API..."
kubectl -n evalforge wait --for=condition=ready pod -l app=api --timeout=120s

# Apply monitoring if files exist
if [ -d infra/k8s/prometheus ]; then
    kubectl apply -f infra/k8s/prometheus/
fi
if [ -d infra/k8s/grafana ]; then
    kubectl create configmap grafana-dashboards \
        --from-file=dashboards.json=infra/k8s/grafana/dashboards.json \
        -n evalforge --dry-run=client -o yaml | kubectl apply -f -
    kubectl apply -f infra/k8s/grafana/
fi

# 5. Port forwards
echo "Setting up port forwards..."
kubectl -n evalforge port-forward svc/api 8000:8000 &
echo "  API: http://localhost:8000"

if kubectl -n evalforge get svc grafana &>/dev/null; then
    kubectl -n evalforge port-forward svc/grafana 3000:3000 &
    echo "  Grafana: http://localhost:3000"
fi

echo ""
echo "=== EvalForge is ready! ==="
echo "  API:     http://localhost:8000"
echo "  Health:  http://localhost:8000/healthz"
echo ""
echo "Run 'make k8s-down' to tear down."
