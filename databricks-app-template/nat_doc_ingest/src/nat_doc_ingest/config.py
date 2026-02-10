from __future__ import annotations

from dataclasses import dataclass
import os
from urllib.parse import urlparse


def _clean(value: str | None) -> str:
    return value.strip() if value else ""


def _normalize_host(host: str) -> str:
    if not host:
        return host
    if host.startswith("http://") or host.startswith("https://"):
        return host.rstrip("/")
    parsed = urlparse(f"https://{host}")
    if parsed.netloc:
        return f"https://{parsed.netloc}"
    return host


@dataclass(frozen=True)
class VectorSearchConfig:
    host: str
    token: str
    endpoint: str
    index_name: str
    embedding_endpoint: str
    primary_key: str
    text_column: str
    embedding_column: str
    chunk_size: int
    chunk_overlap: int
    max_batch_size: int
    create_index: bool


def load_vector_search_config() -> VectorSearchConfig:
    host = _normalize_host(_clean(os.environ.get("DATABRICKS_HOST")))
    token = _clean(os.environ.get("DATABRICKS_TOKEN"))

    if not token:
        token = _clean(os.environ.get("DATABRICKS_API_KEY"))

    endpoint = _clean(os.environ.get("VECTOR_SEARCH_ENDPOINT"))
    index_name = _clean(os.environ.get("VECTOR_SEARCH_INDEX"))
    embedding_endpoint = _clean(os.environ.get("VECTOR_SEARCH_EMBEDDINGS_ENDPOINT"))

    primary_key = _clean(os.environ.get("VECTOR_SEARCH_PRIMARY_KEY")) or "id"
    text_column = _clean(os.environ.get("VECTOR_SEARCH_TEXT_COLUMN")) or "content"
    embedding_column = _clean(os.environ.get("VECTOR_SEARCH_EMBEDDING_COLUMN")) or "embedding"

    chunk_size = int(_clean(os.environ.get("VECTOR_SEARCH_CHUNK_SIZE")) or "1500")
    chunk_overlap = int(_clean(os.environ.get("VECTOR_SEARCH_CHUNK_OVERLAP")) or "200")
    max_batch_size = int(_clean(os.environ.get("VECTOR_SEARCH_BATCH_SIZE")) or "64")
    create_index = _clean(os.environ.get("VECTOR_SEARCH_CREATE_INDEX")).lower() in {
        "1",
        "true",
        "yes",
    }

    missing = []
    if not host:
        missing.append("DATABRICKS_HOST (or DATABRICKS_API_KEY + host)")
    if not token:
        missing.append("DATABRICKS_TOKEN (or DATABRICKS_API_KEY)")
    if not endpoint:
        missing.append("VECTOR_SEARCH_ENDPOINT")
    if not index_name:
        missing.append("VECTOR_SEARCH_INDEX")
    if not embedding_endpoint:
        missing.append("VECTOR_SEARCH_EMBEDDINGS_ENDPOINT")

    if missing:
        raise ValueError("Missing environment variables: " + ", ".join(missing))

    return VectorSearchConfig(
        host=host,
        token=token,
        endpoint=endpoint,
        index_name=index_name,
        embedding_endpoint=embedding_endpoint,
        primary_key=primary_key,
        text_column=text_column,
        embedding_column=embedding_column,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        max_batch_size=max_batch_size,
        create_index=create_index,
    )
