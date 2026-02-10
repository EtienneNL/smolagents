from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class VectorSearchConfig:
    endpoint_name: str
    index_name: str
    text_column: str = "content"
    default_filters: str | None = None
    default_num_results: int = 8

    @classmethod
    def from_env(cls) -> "VectorSearchConfig":
        return cls(
            endpoint_name=os.environ["DATABRICKS_VECTOR_SEARCH_ENDPOINT"],
            index_name=os.environ["DATABRICKS_VECTOR_SEARCH_INDEX"],
            text_column=os.getenv("DATABRICKS_VECTOR_SEARCH_TEXT_COLUMN", "content"),
            default_filters=os.getenv("DATABRICKS_VECTOR_SEARCH_FILTERS"),
            default_num_results=int(
                os.getenv("DATABRICKS_VECTOR_SEARCH_NUM_RESULTS", "8")
            ),
        )
