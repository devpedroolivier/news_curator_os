#!/usr/bin/env bash
# Executa o pipeline de curadoria via API HTTP.
# Uso: ./curate.sh <porta> <endpoint> "<headline>"
#   endpoint: "run" para pipeline rapido, "deep" para curadoria profunda
# Retorna JSON do PipelineRun completo.

set -euo pipefail

PORT="${1:?Porta obrigatoria (ex: 3001)}"
ENDPOINT="${2:?Endpoint obrigatorio: run | deep}"
HEADLINE="${3:?Headline obrigatoria}"

BASE_URL="http://localhost:${PORT}"

# Verifica se o servidor esta rodando
if ! curl -sf "${BASE_URL}/healthz" > /dev/null 2>&1; then
  echo '{"error": "Servidor nao esta rodando na porta '"${PORT}"'. Inicie com: uv run uvicorn news_curator_os.agent_runtime:app --port '"${PORT}"'"}' >&2
  exit 1
fi

# Executa pipeline
curl -sf \
  -X POST \
  -H "Content-Type: application/json" \
  -d "$(printf '{"headline": "%s"}' "$(echo "$HEADLINE" | sed 's/"/\\"/g')")" \
  "${BASE_URL}/api/v1/pipeline/${ENDPOINT}"
