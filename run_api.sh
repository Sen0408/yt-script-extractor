#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

export PATH="/Users/senbing/homebrew/bin:${SCRIPT_DIR}/.venv/bin:${PATH}"

CERT_FILE="$("${SCRIPT_DIR}/.venv/bin/python" -m certifi 2>/dev/null || true)"
if [[ -n "${CERT_FILE}" ]]; then
  export SSL_CERT_FILE="${CERT_FILE}"
  export REQUESTS_CA_BUNDLE="${CERT_FILE}"
fi

if TOKEN="$(security find-generic-password \
  -a VideoBrief \
  -s com.senbing.videobrief.api-token \
  -w 2>/dev/null)"; then
  export VIDEOBRIEF_API_TOKEN="${TOKEN}"
fi

exec .venv/bin/uvicorn api:app --host 0.0.0.0 --port "${VIDEOBRIEF_PORT:-8765}"
