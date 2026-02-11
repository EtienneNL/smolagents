from __future__ import annotations

from pydantic import Field

from nat.builder.builder import Builder
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from .config import load_vector_search_config
from .citations import build_sources_accordion
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


class RetrieveUploadedDocsConfig(FunctionBaseConfig, name="retrieve_uploaded_docs"):
    top_k: int = Field(
        default=5,
        description="Number of chunks to return from vector search.",
    )


@register_function(config_type=RetrieveUploadedDocsConfig)
async def retrieve_uploaded_docs_function(
    config: RetrieveUploadedDocsConfig, builder: Builder
):
    def _retrieve(query: str, top_k: int | None = None) -> list[dict]:
        settings = load_vector_search_config()
        columns = [
            settings.text_column,
            "document_id",
            "chunk_index",
            "source",
            "page_number",
        ]
        results = search_index(
            settings,
            query=query,
            top_k=top_k or config.top_k,
            columns=columns,
        )
        normalized: list[dict] = []
        for result in results:
            content = result.get(settings.text_column) or result.get("content") or ""
            normalized.append(
                {
                    "title": result.get("source") or result.get("title"),
                    "page_index": result.get("page_number") or result.get("page_index"),
                    "content": content,
                    "document_id": result.get("document_id"),
                    "chunk_index": result.get("chunk_index"),
                }
            )
        return normalized

    yield _retrieve


class SearchUploadedDocsWithCitationsConfig(
    FunctionBaseConfig, name="search_uploaded_docs_with_citations"
):
    top_k: int = Field(
        default=5,
        description="Number of chunks to return from vector search.",
    )
    heading: str = Field(
        default="Sources",
        description="Accordion heading label.",
    )


@register_function(config_type=SearchUploadedDocsWithCitationsConfig)
async def search_uploaded_docs_with_citations_function(
    config: SearchUploadedDocsWithCitationsConfig, builder: Builder
):
    def _search(query: str, top_k: int | None = None) -> dict:
        settings = load_vector_search_config()
        columns = [
            settings.text_column,
            "document_id",
            "chunk_index",
            "source",
            "page_number",
        ]
        results = search_index(
            settings,
            query=query,
            top_k=top_k or config.top_k,
            columns=columns,
        )
        accordion = build_sources_accordion(
            results,
            title_key="source",
            page_key="page_number",
            content_key=settings.text_column,
            heading=config.heading,
        )
        return {
            "results": results,
            "accordion_markdown": accordion,
        }

    yield _search
