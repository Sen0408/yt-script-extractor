#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/Users/senbing/homebrew/bin:${PATH}"
PYTHON_BIN="/Users/senbing/homebrew/bin/python3.12"

if [[ ! -x "${ROOT_DIR}/.venv/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${ROOT_DIR}/.venv"
  "${ROOT_DIR}/.venv/bin/python" -m pip install --upgrade pip
  "${ROOT_DIR}/.venv/bin/python" -m pip install -r "${ROOT_DIR}/requirements.txt"
fi

CERT_FILE="$("${ROOT_DIR}/.venv/bin/python" -m certifi 2>/dev/null || true)"
if [[ -n "${CERT_FILE}" ]]; then
  export SSL_CERT_FILE="${CERT_FILE}"
  export REQUESTS_CA_BUNDLE="${CERT_FILE}"
fi

cd "${ROOT_DIR}"
exec "${ROOT_DIR}/.venv/bin/python" main.py "$@"
