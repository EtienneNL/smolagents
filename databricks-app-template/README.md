# Databricks Apps - NeMo Agent Toolkit UI + Backend (single app)

This template runs the NeMo Agent Toolkit backend (NAT) and the UI in a
single Databricks App using repo-run mode (no Dockerfile build). It
highlights the "Runner.run() cannot be called from a running event loop"
issue and shows the safe startup method that avoids it.

## What this template provides
- start.sh that launches NAT and the UI proxy/Next server together.
- Repo-run guidance (no Dockerfile build).

## Assumptions
- You will provide a NAT config file at `./config.yml` (repo root).
- The UI source lives in a folder in the repo.

## Expected layout (recommended)
Place these files in the root of your Databricks App repo:

  .
  ├── app.yaml
  ├── start.sh
  ├── config.yml
  └── NeMo-Agent-Toolkit-UI/

If your UI folder uses a different name, pass UI_SOURCE_DIR at build time.

## Runtime env vars (common)
- NAT_CONFIG_FILE (default: ./config.yml)
- NAT_HOST (default: 0.0.0.0)
- NAT_PORT (internal NAT port, default: 8000 or 8001)
- NAT_BACKEND_URL (UI proxy -> NAT, default: http://127.0.0.1:8000)
- NEXT_INTERNAL_URL (proxy -> Next, default: http://127.0.0.1:3099)
- PORT (public UI port, default: 3000 or 8000)
- DATABRICKS_API_BASE (Databricks serving base URL)
- DATABRICKS_API_KEY (Databricks PAT)

## app.yaml
The provided app.yaml includes environment variables and a `start.sh`
command. Databricks Apps schemas vary by workspace and release channel,
so add any required fields such as name, command/entrypoint, and ports
in your environment.

## LiteLLM Databricks provider (config.yml snippet)
Use the env vars from app.yaml inside your NAT workflow config:

```yaml
llms:
  dbx_llm:
    _type: litellm
    model_name: "databricks/<your-serving-endpoint>"
    api_key: ${DATABRICKS_API_KEY}
    base_url: ${DATABRICKS_API_BASE}
```

## Runner.run() warning and the fix
If you launch NAT using `nat serve` in Databricks repo-run mode, you may see:

```
Error: Runner.run() cannot be called from a running event loop
```

This happens because repo-run apps already have an event loop. The NAT CLI
uses `asyncio.run(...)`, which crashes inside an existing loop.

### Fix (repo-run): use the FastAPI factory with uvicorn
Set the worker class and start uvicorn directly:

```bash
export NAT_FRONT_END_WORKER=nat.front_ends.fastapi.fastapi_front_end_plugin_worker.FastApiFrontEndPluginWorker
uvicorn nat.front_ends.fastapi.main:get_app --factory --host 0.0.0.0 --port 8000
```

## Combined app startup (repo-run)
Use this pattern in `start.sh` to run NAT + UI safely:

```bash
#!/usr/bin/env bash
set -euo pipefail

export NAT_CONFIG_FILE="${NAT_CONFIG_FILE:-./config.yml}"
export NAT_FRONT_END_WORKER="nat.front_ends.fastapi.fastapi_front_end_plugin_worker.FastApiFrontEndPluginWorker"

NAT_PORT="${NAT_PORT:-8001}"
PORT="${PORT:-8000}"

pushd NeMo-Agent-Toolkit-UI
npm ci
npm run build
popd

./NeMo-Agent-Toolkit-UI/node_modules/.bin/concurrently --kill-others --raw \
  "uvicorn nat.front_ends.fastapi.main:get_app --factory --host 0.0.0.0 --port ${NAT_PORT}" \
  "cd NeMo-Agent-Toolkit-UI && PORT=3099 npm run start" \
  "PORT=${PORT} NAT_BACKEND_URL=http://127.0.0.1:${NAT_PORT} NEXT_INTERNAL_URL=http://127.0.0.1:3099 node NeMo-Agent-Toolkit-UI/proxy/server.js"
```

## Notes
- Do not start NAT inside a Python web app or any existing event loop.
- Keep workers=1 and reload=false in your NAT config to avoid duplicate starts.
- WebSocket path must remain /websocket unless you also update the UI proxy.
