#!/usr/bin/env bash
set -euo pipefail

REGISTRY=${1:-"your-registry.example.com/fieldmonitor"}
TAG=${2:-"latest"}

images=(
  "api infra/docker/api.Dockerfile"
  "worker infra/docker/worker.Dockerfile"
  "worker-gpu infra/docker/worker.gpu.Dockerfile"
  "web infra/docker/web.Dockerfile"
  "tiler infra/docker/tiler.Dockerfile"
)

for entry in "${images[@]}"; do
  name=$(echo "$entry" | awk '{print $1}')
  dockerfile=$(echo "$entry" | awk '{print $2}')
  docker buildx build \
    --platform linux/amd64,linux/arm64 \
    -f "$dockerfile" \
    -t "${REGISTRY}/${name}:${TAG}" \
    --push \
    .
done
