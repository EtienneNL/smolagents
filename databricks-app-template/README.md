# Databricks Apps - NeMo Agent Toolkit UI + Backend (single app)

This template runs the NeMo Agent Toolkit backend (NAT) and the UI in a
single Databricks App container. It avoids the "Runner.run() cannot be called
from a running event loop" error by starting NAT as a separate OS process
instead of inside a Python event loop.

## What this template provides
- Dockerfile that builds the UI and installs NAT.
- start.sh that launches NAT and the UI proxy/Next server together.

## Assumptions
- You will provide a NAT config file at /app/config.yml inside the image.
- The UI source lives in a folder in the build context.

## Expected layout (recommended)
Place these files in the root of your Databricks App repo:

  .
  ├── Dockerfile
  ├── start.sh
  ├── config.yml
  └── NeMo-Agent-Toolkit-UI/

If your UI folder uses a different name, pass UI_SOURCE_DIR at build time.

## Build args
- UI_SOURCE_DIR (default: NeMo-Agent-Toolkit-UI)
- NAT_EXTRAS (default: most)

## Runtime env vars
- NAT_CONFIG_FILE (default: /app/config.yml)
- NAT_HOST (default: 0.0.0.0)
- NAT_PORT (default: 8000)
- NAT_BACKEND_URL (default: http://127.0.0.1:8000)
- NEXT_INTERNAL_URL (default: http://127.0.0.1:3099)
- PORT (default: 3000)

## Notes
- Do not start NAT inside a Python web app or any existing event loop.
- Keep workers=1 and reload=false in your NAT config to avoid duplicate starts.
- WebSocket path must remain /websocket unless you also update the UI proxy.
