from __future__ import annotations

from pydantic import Field

from nat.builder.builder import Builder
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from .config import load_vector_search_config
from .vector_search import search_index


class SearchUploadedDocsConfig(FunctionBaseConfig, name="search_uploaded_docs"):
    top_k: int = Field(
        default=5,
        description="Number of chunks to return from vector search.",
    )


@register_function(config_type=SearchUploadedDocsConfig)
async def search_uploaded_docs_function(
    config: SearchUploadedDocsConfig, builder: Builder
):
    def _search(query: str, top_k: int | None = None) -> list[dict]:
        settings = load_vector_search_config()
        columns = [
            settings.text_column,
            "document_id",
            "chunk_index",
            "source",
            "page_number",
        ]
        return search_index(
            settings,
            query=query,
            top_k=top_k or config.top_k,
            columns=columns,
        )

    yield _search
