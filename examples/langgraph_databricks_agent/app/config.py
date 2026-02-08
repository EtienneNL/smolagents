from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DatabricksConfig:
    host: str
    token: str
    model_endpoint: str


def load_config() -> DatabricksConfig:
    host = os.environ.get("DATABRICKS_HOST", "").strip()
    token = os.environ.get("DATABRICKS_TOKEN", "").strip()
    endpoint = os.environ.get("DATABRICKS_MODEL_ENDPOINT", "").strip()

    missing = [
        name
        for name, value in (
            ("DATABRICKS_HOST", host),
            ("DATABRICKS_TOKEN", token),
            ("DATABRICKS_MODEL_ENDPOINT", endpoint),
        )
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing environment variables: " + ", ".join(missing)
        )

    return DatabricksConfig(host=host, token=token, model_endpoint=endpoint)
