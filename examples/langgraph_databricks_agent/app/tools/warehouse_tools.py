from __future__ import annotations

from functools import lru_cache
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_databricks import ChatDatabricks

from ..config import load_config
from ..warehouse import UC_CATALOG, UC_SCHEMA, get_data_from_warehouse

FULL_TABLE_NAME = f"{UC_CATALOG}.{UC_SCHEMA}.b1_nutrient_name_matching"
ALIAS_SPLIT_PATTERN = re.compile(r"[;,|]+")
COLUMN_MEANING_TABLE = f"{UC_CATALOG}.{UC_SCHEMA}.b1_table2_column_meanin"


def _normalize(text: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", cleaned).strip()


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


def _load_column_meaning_rows() -> list[dict]:
    rows = get_data_from_warehouse(
        "SELECT original_column_name, column_meaning, "
        "original_table_name, casual_table_name "
        f"FROM {COLUMN_MEANING_TABLE} WHERE column_meaning IS NOT NULL"
    )
    candidates = []
    for row in rows:
        column_name = "" if row[0] is None else str(row[0])
        column_meaning = "" if row[1] is None else str(row[1])
        original_table = "" if row[2] is None else str(row[2])
        casual_table = "" if row[3] is None else str(row[3])
        normalized_meaning = _normalize(column_meaning)
        if not normalized_meaning:
            continue
        candidates.append(
            {
                "original_column_name": column_name,
                "column_meaning": column_meaning,
                "original_table_name": original_table,
                "casual_table_name": casual_table,
                "normalized_meaning": normalized_meaning,
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


def _limit_candidates_for_llm(
    query_normalized: str,
    candidates: list[dict],
    max_candidates: int = 80,
) -> list[dict]:
    if len(candidates) <= max_candidates:
        return candidates

    tokens = set(query_normalized.split())
    if not tokens:
        return candidates[:max_candidates]

    scored = []
    for candidate in candidates:
        meaning_tokens = set(candidate["normalized_meaning"].split())
        overlap = len(tokens & meaning_tokens)
        if overlap:
            scored.append((overlap, candidate))

    if not scored:
        return candidates[:max_candidates]

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in scored[:max_candidates]]


@lru_cache(maxsize=1)
def _get_similarity_llm() -> ChatDatabricks:
    config = load_config()
    return ChatDatabricks(endpoint=config.model_endpoint, temperature=0)


def _parse_match_index(response_text: str, max_index: int) -> int | None:
    try:
        payload = json.loads(response_text)
        index = int(payload.get("match_index", -1))
        if 0 <= index <= max_index:
            return index
        return None
    except (json.JSONDecodeError, TypeError, ValueError):
        match = re.search(r"(-?\d+)", response_text)
        if not match:
            return None
        index = int(match.group(1))
        if 0 <= index <= max_index:
            return index
        return None


def _select_best_column_match(
    query: str, candidates: list[dict]
) -> dict | None:
    if not candidates:
        return None
    llm = _get_similarity_llm()
    candidate_lines = []
    for index, candidate in enumerate(candidates):
        candidate_lines.append(
            f"{index}) meaning: {candidate['column_meaning']}; "
            f"original_column_name: {candidate['original_column_name']}; "
            f"original_table_name: {candidate['original_table_name']}; "
            f"casual_table_name: {candidate['casual_table_name']}"
        )
    prompt = "\n".join(
        [
            f"User request: {query}",
            "Candidates:",
            *candidate_lines,
            "Return JSON only: {\"match_index\": <0-based index or -1>}",
        ]
    )
    messages = [
        SystemMessage(
            content=(
                "Select the single best semantic match based on column meaning. "
                "If none are relevant, return -1."
            )
        ),
        HumanMessage(content=prompt),
    ]
    response = llm.invoke(messages)
    response_text = response.content if hasattr(response, "content") else str(response)
    match_index = _parse_match_index(response_text, len(candidates) - 1)
    if match_index is None:
        return None
    return candidates[match_index]


@tool
def match_nutrient_names(
    query: list[str] | str,
    top_k: int | None = None,
) -> list[dict]:
    """Match nutrient aliases against the UC matching table.

    Args:
        query: One or more nutrient mentions (e.g., ["prot", "fat"]).
        top_k: Optional max number of matches to return.

    Returns:
        A list of results for each query, each with:
        {
          "query": <raw_query>,
          "normalized_query": <normalized_query>,
          "matches": [
            {
              "nutr_name": <matched_name>,
              "nutr_code": <matched_code>,
              "nutr_alias": <matched_alias>
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
            for alias_entry in candidate["aliases"]:
                if query_norm == alias_entry["normalized"]:
                    matches.append(
                        {
                            "nutr_name": candidate["nutr_name"],
                            "nutr_code": candidate["nutr_code"],
                            "nutr_alias": alias_entry["alias"],
                        }
                    )
                    break
        if top_k is None:
            limited_matches = matches
        else:
            limited_matches = matches[: max(top_k, 0)]
        results.append(
            {
                "query": query_entry["raw"],
                "normalized_query": query_norm,
                "matches": limited_matches,
            }
        )
    return results


@tool
def match_column_names(
    query: list[str] | str,
) -> list[dict]:
    """Match user-described column meanings to column names using LLM similarity.

    Args:
        query: One or more column-meaning mentions.

    Returns:
        A list of results for each query, each with:
        {
          "query": <raw_query>,
          "normalized_query": <normalized_query>,
          "match": {
            "original_column_name": <column_name>,
            "column_meaning": <meaning>,
            "original_table_name": <table_name>,
            "casual_table_name": <casual_name>
          } | null
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

    candidates = _load_column_meaning_rows()
    results = []
    for query_entry in normalized_queries:
        query_norm = query_entry["normalized"]
        limited_candidates = _limit_candidates_for_llm(
            query_norm, candidates
        )
        best_match = _select_best_column_match(
            query_entry["raw"], limited_candidates
        )
        results.append(
            {
                "query": query_entry["raw"],
                "normalized_query": query_norm,
                "match": (
                    {
                        "original_column_name": best_match[
                            "original_column_name"
                        ],
                        "column_meaning": best_match["column_meaning"],
                        "original_table_name": best_match[
                            "original_table_name"
                        ],
                        "casual_table_name": best_match["casual_table_name"],
                    }
                    if best_match
                    else None
                ),
            }
        )
    return results
