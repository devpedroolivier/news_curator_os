#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
source .env
set +a

BASE_URL="http://127.0.0.1:${APP_PORT}"

echo "healthz:"
curl -fsS "${BASE_URL}/healthz"
echo
echo "readyz:"
curl -fsS "${BASE_URL}/readyz"
echo
echo "monitoring summary:"
curl -fsS "${BASE_URL}/api/v1/monitoring/summary"
echo
