#!/usr/bin/env bash
# Verifica se o servidor esta rodando e retorna status.
# Uso: ./check_server.sh [porta]

PORT="${1:-8000}"
BASE_URL="http://localhost:${PORT}"

if curl -sf "${BASE_URL}/healthz" 2>/dev/null; then
  echo ""
  echo "SERVER_STATUS=running PORT=${PORT}"
else
  echo '{"status": "offline"}'
  echo "SERVER_STATUS=offline PORT=${PORT}"
  exit 1
fi
