#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ $# -lt 1 ]]; then
  echo "uso: ./scripts/run_terminal_batch.sh <arquivo.txt|arquivo.csv> [--mode flow|workflow] [--persist] [--stream] [--output-json arquivo.json]" >&2
  exit 1
fi

set -a
source .env
set +a

exec ./.venv/bin/python -m news_curator_os.cli batch "$@"
