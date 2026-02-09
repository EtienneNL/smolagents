# LangGraph Databricks Tool-Calling Agent (Python 3.11)

This scaffold demonstrates a minimal LangGraph agent that uses a tool-calling
node (`ToolNode`) and a Databricks-hosted model via LangChain's Databricks API.

## Requirements

- Python 3.11
- A Databricks workspace with a model serving endpoint

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure Databricks credentials and endpoint:
   ```bash
   export DATABRICKS_HOST="https://<your-workspace-host>"
   export DATABRICKS_TOKEN="<your-personal-access-token>"
   export DATABRICKS_MODEL_ENDPOINT="<your-model-serving-endpoint-name>"
   export DATABRICKS_SERVER_HOSTNAME="<your-workspace-hostname>"
   export DATABRICKS_HTTP_PATH="<your-sql-warehouse-http-path>"
   export DATABRICKS_UC_CATALOG="uc-specializednutrition-rnd-prd-001"
   export DATABRICKS_UC_SCHEMA="sn_quality_control_dev"
   ```

3. Run the example:
   ```bash
   python -m app.main
   ```

## Project layout

```
langgraph_databricks_agent/
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── graph.py
│   ├── main.py
│   └── tools/
│       ├── __init__.py
│       ├── math_tools.py
│       └── time_tools.py
├── requirements.txt
└── README.md
```

## Notes

- Add new tools inside `app/tools/` and include them in `app/tools/__init__.py`.
- The scaffold is intentionally small so you can adapt it to your own tool set.
