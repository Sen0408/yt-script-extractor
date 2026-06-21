#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLOUDFLARED="/Users/senbing/homebrew/opt/cloudflared/bin/cloudflared"
GH="/Users/senbing/homebrew/bin/gh"
GIST_ID="0b9144dcaf55de408887209419baf58b"
LOG_FILE="${SCRIPT_DIR}/tunnel.log"
API_TOKEN="$(
  security find-generic-password \
    -a VideoBrief \
    -s com.senbing.videobrief.api-token \
    -w
)"

: > "${LOG_FILE}"
"${CLOUDFLARED}" tunnel \
  --no-autoupdate \
  --url http://127.0.0.1:8765 \
  > "${LOG_FILE}" 2>&1 &
TUNNEL_PID=$!

cleanup() {
  kill "${TUNNEL_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

TUNNEL_URL=""
for _ in $(seq 1 60); do
  if ! kill -0 "${TUNNEL_PID}" 2>/dev/null; then
    wait "${TUNNEL_PID}"
  fi

  TUNNEL_URL="$(
    sed -nE 's#.*(https://[a-z0-9-]+\.trycloudflare\.com).*#\1#p' \
      "${LOG_FILE}" \
      | head -1
  )"
  if [[ -n "${TUNNEL_URL}" ]]; then
    break
  fi
  sleep 1
done

if [[ -z "${TUNNEL_URL}" ]]; then
  echo "Cloudflare tunnel URL was not created" >> "${LOG_FILE}"
  exit 1
fi

for _ in $(seq 1 30); do
  if curl \
    --doh-url https://cloudflare-dns.com/dns-query \
    -fsS \
    --max-time 5 \
    -H "X-VideoBrief-Token: ${API_TOKEN}" \
    "${TUNNEL_URL}/api/health" \
    > /dev/null; then
    break
  fi
  sleep 1
done

ENDPOINT_JSON="$(
  /usr/bin/jq -nc \
    --arg url "${TUNNEL_URL}" \
    --arg updated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{url: $url, updated_at: $updated_at}'
)"
GIST_UPDATE="$(
  /usr/bin/jq -nc \
    --arg content "${ENDPOINT_JSON}" \
    '{files: {"videobrief-endpoint.json": {content: $content}}}'
)"

printf '%s' "${GIST_UPDATE}" \
  | "${GH}" api \
      --method PATCH \
      "gists/${GIST_ID}" \
      --input - \
      > /dev/null 2>> "${LOG_FILE}"

wait "${TUNNEL_PID}"
