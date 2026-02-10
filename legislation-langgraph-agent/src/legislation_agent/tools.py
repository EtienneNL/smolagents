from __future__ import annotations

from typing import Any, Optional

from databricks.vector_search.client import VectorSearchClient
from langchain_core.tools import tool

from .config import VectorSearchConfig


def _format_results(results: list[dict[str, Any]]) -> str:
    if not results:
        return "No results found."

    formatted = []
    for idx, item in enumerate(results, start=1):
        text = item.get("text") or item.get("page_content") or ""
        metadata = item.get("metadata") or {}
        score = item.get("score")
        formatted.append(
            f"Result {idx} (score={score})\n{text}\nMetadata: {metadata}"
        )
    return "\n\n".join(formatted)


def build_hybrid_retriever_tool(config: VectorSearchConfig):
    client = VectorSearchClient()
    index = client.get_index(
        endpoint_name=config.endpoint_name,
        index_name=config.index_name,
    )

    @tool("hybrid_retriever")
    def hybrid_retriever(
        query: str,
        filters: Optional[str] = None,
        num_results: Optional[int] = None,
    ) -> str:
        """Hybrid search over Databricks Vector Search with optional filters."""
        effective_filters = filters if filters is not None else config.default_filters
        effective_num_results = (
            num_results if num_results is not None else config.default_num_results
        )

        search_kwargs: dict[str, Any] = {
            "query_text": query,
            "query_type": "hybrid",
            "num_results": effective_num_results,
        }
        if effective_filters:
            search_kwargs["filters"] = effective_filters

        results = index.similarity_search(**search_kwargs)
        return _format_results(results)

    return hybrid_retriever
