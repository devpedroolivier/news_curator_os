#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

set -a
source .env
set +a

UVICORN_ARGS=(news_curator_os.agent_runtime:app --host "${APP_HOST}" --port "${APP_PORT}")

if [[ "${APP_RELOAD,,}" == "true" ]]; then
  UVICORN_ARGS+=(--reload)
fi

exec ./.venv/bin/python -m uvicorn "${UVICORN_ARGS[@]}"
