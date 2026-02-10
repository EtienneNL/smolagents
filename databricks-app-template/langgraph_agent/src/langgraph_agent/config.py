from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


@dataclass(frozen=True)
class DatabricksConfig:
    host: str
    token: str
    model_endpoint: str | None
    http_path: str
    server_hostname: str


def _clean(value: str | None) -> str:
    return value.strip() if value else ""


def _infer_host_from_api_base(api_base: str) -> str:
    if not api_base:
        return ""
    parsed = urlparse(api_base)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    parsed = urlparse(f"https://{api_base}")
    if parsed.netloc:
        return f"https://{parsed.netloc}"
    return api_base


def _infer_server_hostname(host: str) -> str:
    if not host:
        return ""
    parsed = urlparse(host if "://" in host else f"https://{host}")
    return parsed.netloc or host


def load_config(*, require_model_endpoint: bool = True) -> DatabricksConfig:
    host = _clean(os.environ.get("DATABRICKS_HOST"))
    token = _clean(os.environ.get("DATABRICKS_TOKEN"))
    model_endpoint = _clean(os.environ.get("DATABRICKS_MODEL_ENDPOINT"))
    http_path = _clean(os.environ.get("DATABRICKS_HTTP_PATH"))
    server_hostname = _clean(os.environ.get("DATABRICKS_SERVER_HOSTNAME"))

    if not token:
        token = _clean(os.environ.get("DATABRICKS_API_KEY"))
    if not host:
        host = _infer_host_from_api_base(_clean(os.environ.get("DATABRICKS_API_BASE")))
    if not model_endpoint:
        model_endpoint = _clean(os.environ.get("DATABRICKS_SERVING_ENDPOINT"))
    if not server_hostname:
        server_hostname = _infer_server_hostname(host)

    missing = []
    if not host:
        missing.append("DATABRICKS_HOST (or DATABRICKS_API_BASE)")
    if not token:
        missing.append("DATABRICKS_TOKEN (or DATABRICKS_API_KEY)")
    if require_model_endpoint and not model_endpoint:
        missing.append("DATABRICKS_MODEL_ENDPOINT (or DATABRICKS_SERVING_ENDPOINT)")
    if not http_path:
        missing.append("DATABRICKS_HTTP_PATH")
    if not server_hostname:
        missing.append("DATABRICKS_SERVER_HOSTNAME")

    if missing:
        raise ValueError("Missing environment variables: " + ", ".join(missing))

    return DatabricksConfig(
        host=host,
        token=token,
        model_endpoint=model_endpoint or None,
        http_path=http_path,
        server_hostname=server_hostname,
    )
