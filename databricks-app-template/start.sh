#!/usr/bin/env bash
set -euo pipefail

NAT_CONFIG_FILE="${NAT_CONFIG_FILE:-/app/config.yml}"
NAT_HOST="${NAT_HOST:-0.0.0.0}"
NAT_PORT="${NAT_PORT:-8000}"

export NAT_BACKEND_URL="${NAT_BACKEND_URL:-http://127.0.0.1:${NAT_PORT}}"
export NEXT_INTERNAL_URL="${NEXT_INTERNAL_URL:-http://127.0.0.1:3099}"
export PORT="${PORT:-3000}"

exec npx concurrently --kill-others --raw \
  "nat serve --config_file \"${NAT_CONFIG_FILE}\" --host \"${NAT_HOST}\" --port \"${NAT_PORT}\"" \
  "PORT=3099 node server.js" \
  "PORT=${PORT} node proxy/server.js"
