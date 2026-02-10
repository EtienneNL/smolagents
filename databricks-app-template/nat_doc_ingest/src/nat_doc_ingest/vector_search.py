from __future__ import annotations

import logging
from typing import Any
import uuid

import requests
from databricks.vector_search.client import VectorSearchClient

from .config import VectorSearchConfig

logger = logging.getLogger(__name__)


def _request_embeddings(config: VectorSearchConfig, texts: list[str]) -> list[list[float]]:
    url = f"{config.host}/serving-endpoints/{config.embedding_endpoint}/invocations"
    headers = {"Authorization": f"Bearer {config.token}"}
    payload = {"input": texts}
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict) and "data" in data:
        return [item["embedding"] for item in data["data"]]
    if isinstance(data, dict) and "embeddings" in data:
        return data["embeddings"]
    if isinstance(data, list):
        return data
    raise ValueError("Unexpected embeddings response format from Databricks serving.")


def _get_vector_search_client(config: VectorSearchConfig) -> VectorSearchClient:
    return VectorSearchClient(
        workspace_url=config.host,
        personal_access_token=config.token,
    )


def _ensure_index(
    config: VectorSearchConfig, embedding_dimension: int
) -> None:
    if not config.create_index:
        return
    client = _get_vector_search_client(config)
    try:
        client.get_index(config.endpoint, config.index_name)
        return
    except Exception:
        logger.info("Vector search index not found; creating %s", config.index_name)

    schema = {
        config.primary_key: "string",
        config.text_column: "string",
        config.embedding_column: "array<float>",
        "document_id": "string",
        "chunk_index": "int",
        "source": "string",
        "page_number": "int",
    }
    client.create_direct_access_index(
        endpoint_name=config.endpoint,
        index_name=config.index_name,
        primary_key=config.primary_key,
        embedding_dimension=embedding_dimension,
        embedding_vector_column=config.embedding_column,
        schema=schema,
    )


def index_documents(
    config: VectorSearchConfig,
    *,
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    if not documents:
        return {"indexed": 0}

    texts = [doc[config.text_column] for doc in documents]
    embeddings = _request_embeddings(config, texts)
    if len(embeddings) != len(documents):
        raise ValueError("Embeddings count does not match chunk count.")

    for doc, embedding in zip(documents, embeddings, strict=False):
        doc[config.embedding_column] = embedding

    _ensure_index(config, len(embeddings[0]))

    client = _get_vector_search_client(config)
    index = client.get_index(config.endpoint, config.index_name)

    batch_size = max(1, config.max_batch_size)
    for start in range(0, len(documents), batch_size):
        batch = documents[start : start + batch_size]
        index.upsert(batch)

    return {"indexed": len(documents)}


def build_chunk_records(
    *,
    document_id: str | None,
    source: str,
    chunks: list[dict[str, Any]],
    config: VectorSearchConfig,
) -> list[dict[str, Any]]:
    doc_id = document_id or str(uuid.uuid4())
    records: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk_id = str(uuid.uuid4())
        record = {
            config.primary_key: chunk_id,
            config.text_column: chunk["text"],
            "document_id": doc_id,
            "chunk_index": chunk["chunk_index"],
            "source": source,
            "page_number": chunk.get("page_number"),
        }
        records.append(record)
    return records


def search_index(
    config: VectorSearchConfig,
    *,
    query: str,
    top_k: int,
    columns: list[str],
) -> list[dict[str, Any]]:
    client = _get_vector_search_client(config)
    index = client.get_index(config.endpoint, config.index_name)

    if hasattr(index, "similarity_search"):
        return index.similarity_search(
            query_text=query,
            columns=columns,
            num_results=top_k,
        )

    embedding = _request_embeddings(config, [query])[0]
    if hasattr(index, "query"):
        return index.query(
            query_vector=embedding,
            columns=columns,
            num_results=top_k,
        )

    raise RuntimeError("Vector search index does not support query methods.")
