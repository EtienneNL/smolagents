#!/usr/bin/env bash
set -euo pipefail

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: Node.js is required for the UI in repo-run mode."
  exit 1
fi

export NAT_CONFIG_FILE="${NAT_CONFIG_FILE:-./config.yml}"
export NAT_FRONT_END_WORKER="${NAT_FRONT_END_WORKER:-nat.front_ends.fastapi.fastapi_front_end_plugin_worker.FastApiFrontEndPluginWorker}"

NAT_PORT="${NAT_PORT:-8001}"
PORT="${PORT:-8000}"

if [ -d "./nat_mlflow_feedback" ]; then
  pip install -e ./nat_mlflow_feedback
fi

if [ -d "./nat_doc_ingest" ]; then
  pip install -e ./nat_doc_ingest
fi

if [ -d "./langgraph_agent" ]; then
  pip install -e ./langgraph_agent
fi

if [ -d "./CLIMATE_ASSISTANT" ]; then
  pip install -e ./CLIMATE_ASSISTANT
fi

pushd NeMo-Agent-Toolkit-UI >/dev/null
npm ci
npm run build
popd >/dev/null

./NeMo-Agent-Toolkit-UI/node_modules/.bin/concurrently --kill-others --raw \
  "uvicorn nat.front_ends.fastapi.main:get_app --factory --host 0.0.0.0 --port ${NAT_PORT}" \
  "cd NeMo-Agent-Toolkit-UI && PORT=3099 npm run start" \
  "PORT=${PORT} NAT_BACKEND_URL=http://127.0.0.1:${NAT_PORT} NEXT_INTERNAL_URL=http://127.0.0.1:3099 node NeMo-Agent-Toolkit-UI/proxy/server.js"
