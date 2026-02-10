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

## LangGraph agent bridge (optional)
If you want to reuse a LangGraph workflow inside your NeMo Agent Toolkit
workflow, this repo includes a lightweight plugin under `langgraph_agent/`.
It exposes:

- `langgraph_agent` (invokes the compiled LangGraph workflow)
- `match_nutrient_names`, `match_column_names`, `query_nutrient_data`

`start.sh` installs the package automatically when the folder exists.

### config.yml snippet
```yaml
functions:
  langgraph_agent:
    _type: langgraph_agent
    # Optional override:
    # system_prompt: "..."

  match_nutrient_names:
    _type: match_nutrient_names

  match_column_names:
    _type: match_column_names

  query_nutrient_data:
    _type: query_nutrient_data

workflow:
  _type: react_agent
  llm_name: dbx_llm
  tool_names:
    - match_nutrient_names
    - match_column_names
    - query_nutrient_data
    - langgraph_agent
```

### Required env vars
The LangGraph tools reuse the same Databricks environment variables used by
NAT, with a few extras for SQL access:

- `DATABRICKS_HOST` (fallback: `DATABRICKS_API_BASE`)
- `DATABRICKS_TOKEN` (fallback: `DATABRICKS_API_KEY`)
- `DATABRICKS_MODEL_ENDPOINT` (fallback: `DATABRICKS_SERVING_ENDPOINT`)
- `DATABRICKS_HTTP_PATH`
- `DATABRICKS_SERVER_HOSTNAME`
- `DATABRICKS_UC_CATALOG`, `DATABRICKS_UC_SCHEMA` (optional overrides)

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

## MLflow feedback telemetry (local to Databricks)
This repo includes a lightweight MLflow telemetry + feedback plugin under
`nat_mlflow_feedback/`. It:

- Creates an MLflow run per workflow request
- Sets `observability_trace_id` to the MLflow `run_id`
- Exposes `/feedback` to log 👍/👎 to the run

### Enable the plugin
1) Install the plugin in `start.sh` (already handled if the folder exists):
```bash
pip install -e ./nat_mlflow_feedback
```

2) Set the front-end worker (repo-run requires this env var):
```bash
export NAT_FRONT_END_WORKER=nat_mlflow_feedback.fastapi_plugin_worker.MlflowFastAPIPluginWorker
```

3) Add telemetry config to `config.yml`:
```yaml
general:
  telemetry:
    tracing:
      mlflow:
        _type: mlflow
        experiment_name: ${MLFLOW_EXPERIMENT_NAME}
        tracking_uri: ${MLFLOW_TRACKING_URI:-}
```

4) Set environment variables in `app.yaml`:
```yaml
- name: NAT_FRONT_END_WORKER
  value: nat_mlflow_feedback.fastapi_plugin_worker.MlflowFastAPIPluginWorker
- name: MLFLOW_EXPERIMENT_NAME
  value: nat-feedback
```

> The UI thumbs-up/down buttons call `/feedback` automatically once
> `observability_trace_id` is present.

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
