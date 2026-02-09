from __future__ import annotations

from difflib import SequenceMatcher
import os
import re
from typing import Iterable

from databricks import sql
from langchain_core.tools import tool

FULL_TABLE_NAME = (
    "uc-specializednutrition-rnd-prd-001."
    "sn_quality_control_dev.b1_nutrient_name_matching"
)


def get_warehouse_connection():
    return sql.connect(
        server_hostname=os.environ["DATABRICKS_SERVER_HOSTNAME"],
        http_path=os.environ["DATABRICKS_HTTP_PATH"],
        access_token=os.environ["DATABRICKS_TOKEN"],
    )


def get_data_from_warehouse(statement: str):
    connection = get_warehouse_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement)
            rows = cursor.fetchall()
            return rows
    except Exception as exc:
        if "Invalid SessionHandle" in str(exc):
            connection = get_warehouse_connection()
            with connection.cursor() as cursor:
                cursor.execute(statement)
                rows = cursor.fetchall()
                return rows
        raise


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


def _score_match(query: str, candidate: str) -> float:
    return SequenceMatcher(None, _normalize(query), _normalize(candidate)).ratio()


def _describe_table_columns(table_name: str) -> list[str]:
    rows = get_data_from_warehouse(f"DESCRIBE TABLE {table_name}")
    columns: list[str] = []
    for row in rows:
        col_name = str(row[0]).strip()
        if not col_name or col_name.startswith("#"):
            continue
        columns.append(col_name)
    return columns


def _pick_name_column(columns: Iterable[str]) -> str:
    preferred = ("nutrient", "name", "label", "description")
    for column in columns:
        lowered = column.casefold()
        if any(key in lowered for key in preferred):
            return column
    return next(iter(columns))


def _load_candidate_names(column_name: str | None) -> list[str]:
    columns = _describe_table_columns(FULL_TABLE_NAME)
    if not columns:
        raise ValueError(
            f"No columns found for table {FULL_TABLE_NAME}."
        )
    resolved_column = column_name or _pick_name_column(columns)
    rows = get_data_from_warehouse(
        f"SELECT DISTINCT {resolved_column} FROM {FULL_TABLE_NAME} "
        f"WHERE {resolved_column} IS NOT NULL"
    )
    candidates = []
    for row in rows:
        value = row[0]
        if value is None:
            continue
        candidates.append(str(value))
    return candidates


@tool
def match_nutrient_names(
    query: str,
    top_k: int = 5,
    min_score: float = 0.6,
    column_name: str | None = None,
) -> list[dict]:
    """Fuzzy match a nutrient name against the UC matching table.

    Args:
        query: User-provided nutrient name (e.g., "prot").
        top_k: Max number of matches to return.
        min_score: Minimum similarity score (0-1) to include.
        column_name: Optional override for the column containing names.

    Returns:
        A list of matches sorted by score (desc), each with:
        {"name": <matched_name>, "score": <0-1>}
    """
    if not query.strip():
        return []

    candidates = _load_candidate_names(column_name)
    scored = []
    for candidate in candidates:
        score = _score_match(query, candidate)
        if score >= min_score:
            scored.append({"name": candidate, "score": score})

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(top_k, 0)]
