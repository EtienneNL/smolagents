from __future__ import annotations

from difflib import SequenceMatcher
import re

from langchain_core.tools import tool

from ..warehouse import UC_CATALOG, UC_SCHEMA, get_data_from_warehouse

FULL_TABLE_NAME = f"{UC_CATALOG}.{UC_SCHEMA}.b1_nutrient_name_matching"
ALIAS_SPLIT_PATTERN = re.compile(r"[;,|]+")


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


def _score_normalized(query: str, candidate: str) -> float:
    return SequenceMatcher(None, query, candidate).ratio()


def _split_aliases(raw_aliases: str) -> list[str]:
    parts = ALIAS_SPLIT_PATTERN.split(raw_aliases)
    cleaned = []
    for part in parts:
        trimmed = part.strip()
        if trimmed:
            cleaned.append(trimmed)
    return cleaned


def _load_nutrient_alias_rows() -> list[dict]:
    rows = get_data_from_warehouse(
        "SELECT nutr_name, nutr_code, nutr_alias "
        f"FROM {FULL_TABLE_NAME} WHERE nutr_alias IS NOT NULL"
    )
    candidates = []
    for row in rows:
        nutr_name = "" if row[0] is None else str(row[0])
        nutr_code = "" if row[1] is None else str(row[1])
        raw_aliases = "" if row[2] is None else str(row[2])
        aliases = _split_aliases(raw_aliases) or [raw_aliases.strip()]
        alias_entries = []
        for alias in aliases:
            normalized_alias = _normalize(alias)
            if not normalized_alias:
                continue
            alias_entries.append(
                {
                    "alias": alias,
                    "normalized": normalized_alias,
                }
            )
        if not alias_entries:
            continue
        candidates.append(
            {
                "nutr_name": nutr_name,
                "nutr_code": nutr_code,
                "aliases": alias_entries,
            }
        )
    return candidates


def _split_queries(raw_query: str) -> list[str]:
    if not raw_query.strip():
        return []
    parts = re.split(r"[;,]+", raw_query)
    if len(parts) == 1:
        parts = re.split(r"\s+and\s+", raw_query, flags=re.IGNORECASE)
    cleaned = []
    for part in parts:
        trimmed = part.strip()
        if trimmed:
            cleaned.append(trimmed)
    return cleaned


def _normalize_queries(queries: list[str]) -> list[dict]:
    normalized = []
    for query in queries:
        normalized_query = _normalize(query)
        if normalized_query:
            normalized.append(
                {
                    "raw": query,
                    "normalized": normalized_query,
                }
            )
    return normalized


@tool
def match_nutrient_names(
    query: list[str] | str,
    top_k: int = 5,
    min_score: float = 0.6,
) -> list[dict]:
    """Fuzzy match nutrient aliases against the UC matching table.

    Args:
        query: One or more nutrient mentions (e.g., ["prot", "fat"]).
        top_k: Max number of matches to return.
        min_score: Minimum similarity score (0-1) to include.

    Returns:
        A list of results for each query, each with:
        {
          "query": <raw_query>,
          "normalized_query": <normalized_query>,
          "matches": [
            {
              "nutr_name": <matched_name>,
              "nutr_code": <matched_code>,
              "nutr_alias": <matched_alias>,
              "score": <0-1>
            }
          ]
        }
    """
    if isinstance(query, str):
        query_list = _split_queries(query)
    else:
        query_list = []
        for item in query:
            query_list.extend(_split_queries(str(item)))

    normalized_queries = _normalize_queries(query_list)
    if not normalized_queries:
        return []

    candidates = _load_nutrient_alias_rows()
    results = []
    for query_entry in normalized_queries:
        query_norm = query_entry["normalized"]
        matches = []
        for candidate in candidates:
            best_score = 0.0
            best_alias = ""
            for alias_entry in candidate["aliases"]:
                score = _score_normalized(query_norm, alias_entry["normalized"])
                if score > best_score:
                    best_score = score
                    best_alias = alias_entry["alias"]
            if best_score >= min_score:
                matches.append(
                    {
                        "nutr_name": candidate["nutr_name"],
                        "nutr_code": candidate["nutr_code"],
                        "nutr_alias": best_alias,
                        "score": best_score,
                    }
                )

        matches.sort(key=lambda item: item["score"], reverse=True)
        results.append(
            {
                "query": query_entry["raw"],
                "normalized_query": query_norm,
                "matches": matches[: max(top_k, 0)],
            }
        )
    return results
