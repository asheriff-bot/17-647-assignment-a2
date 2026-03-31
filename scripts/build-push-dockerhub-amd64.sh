#!/usr/bin/env bash
# Build all four A2 images for linux/amd64 (EC2 t3.micro / Amazon Linux) and push to Docker Hub.
#
# Usage (from repo root):
#   ./scripts/build-push-dockerhub-amd64.sh
# Optional overrides:
#   export DH=otheruser      # default: akramdocke
#   export TAG=a2-2-latest   # default: a21-latest
#
# Prerequisites:
#   docker login
#   On Apple Silicon: if build fails, run once:
#     docker buildx create --name amd64builder --driver docker-container --use
#     docker buildx inspect amd64builder --bootstrap

set -euo pipefail

DH="${DH:-akramdocke}"
TAG="${TAG:-a21-latest}"

PLATFORM="linux/amd64"

echo "Building for ${PLATFORM} and pushing to Docker Hub as ${DH}/*:${TAG}"

if ! docker buildx version >/dev/null 2>&1; then
  echo "docker buildx not found; install Docker Desktop or docker buildx plugin."
  exit 1
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

build_push() {
  local context="$1"
  local dockerfile="$2"
  local image="$3"
  docker buildx build \
    --platform "${PLATFORM}" \
    --push \
    -f "${dockerfile}" \
    -t "${DH}/${image}:${TAG}" \
    "${context}"
}

build_push "./customer_service" "customer_service/Dockerfile" "bookstore-customer-service"
build_push "./book_service" "book_service/Dockerfile" "bookstore-book-service"
build_push "." "web_bff/Dockerfile" "bookstore-web-bff"
build_push "." "mobile_bff/Dockerfile" "bookstore-mobile-bff"

echo "Done. On EC2 (amd64), run:"
echo "  docker pull ${DH}/bookstore-customer-service:${TAG}"
echo "  docker pull ${DH}/bookstore-book-service:${TAG}"
echo "  docker pull ${DH}/bookstore-web-bff:${TAG}"
echo "  docker pull ${DH}/bookstore-mobile-bff:${TAG}"
