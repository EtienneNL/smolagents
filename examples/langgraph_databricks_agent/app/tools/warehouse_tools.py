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
IDENTIFIER_SIMPLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
IDENTIFIER_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
ALIAS_SPLIT_PATTERN = re.compile(r"[;,|]+")
COLUMN_MEANING_TABLE = f"{UC_CATALOG}.{UC_SCHEMA}.b1_table2_column_meaning"
SPEC_PREFIX = "2"
CHANGE_PREFIX = "5"
SPEC_ZERO_PADDING = "0000000"


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


@lru_cache(maxsize=1)
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


@lru_cache(maxsize=1)
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


def _escape_sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _dedupe_preserve(items: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _split_values(raw_values: str) -> list[str]:
    parts = re.split(r"[;,]+", raw_values)
    if len(parts) == 1:
        parts = re.split(r"\s+and\s+", raw_values, flags=re.IGNORECASE)
    cleaned = []
    for part in parts:
        trimmed = part.strip()
        if trimmed:
            cleaned.append(trimmed)
    return cleaned


def _normalize_spec_change(value: str, prefix: str) -> list[str]:
    digits = "".join(re.findall(r"\d", str(value)))
    if not digits:
        return []

    candidates = []
    full_pattern = rf"^{re.escape(prefix)}0{{7}}\d{{4}}$"
    if re.match(full_pattern, digits):
        candidates.append(digits)

    if len(digits) >= 4:
        last_four = digits[-4:]
        candidates.append(f"{prefix}{SPEC_ZERO_PADDING}{last_four}")

    return _dedupe_preserve(candidates)


def _safe_identifier(name: str) -> str:
    if IDENTIFIER_SIMPLE_PATTERN.match(name):
        return name
    if IDENTIFIER_SAFE_PATTERN.match(name) and "`" not in name:
        return f"`{name}`"
    raise ValueError(f"Unsafe identifier: {name!r}")


def _qualify_table_name(table_name: str) -> str:
    if "." in table_name:
        parts = table_name.split(".")
        if len(parts) not in {2, 3}:
            raise ValueError(f"Unexpected table name format: {table_name!r}")
        safe_parts = [_safe_identifier(part) for part in parts]
        return ".".join(safe_parts)
    return f"{_safe_identifier(UC_CATALOG)}.{_safe_identifier(UC_SCHEMA)}.{_safe_identifier(table_name)}"


def _extract_nutrient_values(
    nutrient_input: list | str, preferred_key: str
) -> list[str]:
    values: list[str] = []
    if isinstance(nutrient_input, str):
        values.extend(_split_values(nutrient_input))
    else:
        for item in nutrient_input:
            if isinstance(item, str):
                values.extend(_split_values(item))
            elif isinstance(item, dict):
                if "matches" in item:
                    for match in item.get("matches", []):
                        value = match.get(preferred_key)
                        if value:
                            values.append(str(value))
                else:
                    value = item.get(preferred_key)
                    if value:
                        values.append(str(value))
    return _dedupe_preserve(values)


def _extract_column_names(column_input: list | str) -> list[str]:
    columns: list[str] = []
    if isinstance(column_input, str):
        columns.extend(_split_values(column_input))
    else:
        for item in column_input:
            if isinstance(item, str):
                columns.extend(_split_values(item))
            elif isinstance(item, dict):
                if "matches" in item:
                    for match in item.get("matches", []):
                        column_name = match.get("original_column_name")
                        if column_name:
                            columns.append(str(column_name))
                else:
                    column_name = item.get("original_column_name")
                    if column_name:
                        columns.append(str(column_name))
    return _dedupe_preserve(columns)


def _infer_unit_from_text(text: str) -> str | None:
    normalized = text.casefold()
    if (
        "per 100 g" in normalized
        or "per 100g" in normalized
        or "per_100g" in normalized
        or "per100g" in normalized
        or "per 100 g" in normalized.replace("_", " ")
    ):
        return "per 100 g"
    if (
        "per 100 kj" in normalized
        or "per 100kj" in normalized
        or "per_100kj" in normalized
        or "per100kj" in normalized
        or "per 100 kj" in normalized.replace("_", " ")
    ):
        return "per 100 kJ"
    if (
        "percent" in normalized
        or "percentage" in normalized
        or "pct" in normalized
        or "%" in normalized
    ):
        return "percent"
    return None


def _extract_column_units(column_input: list | str) -> dict[str, str | None]:
    units: dict[str, str | None] = {}

    def set_unit(column_name: str, meaning: str | None = None) -> None:
        text = column_name
        if meaning:
            text = f"{column_name} {meaning}"
        unit = _infer_unit_from_text(text)
        units[column_name] = unit

    if isinstance(column_input, str):
        for name in _split_values(column_input):
            set_unit(name)
    else:
        for item in column_input:
            if isinstance(item, str):
                for name in _split_values(item):
                    set_unit(name)
            elif isinstance(item, dict):
                if "matches" in item:
                    for match in item.get("matches", []):
                        column_name = match.get("original_column_name")
                        if column_name:
                            set_unit(
                                str(column_name),
                                match.get("column_meaning"),
                            )
                else:
                    column_name = item.get("original_column_name")
                    if column_name:
                        set_unit(
                            str(column_name),
                            item.get("column_meaning"),
                        )
    return units


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


def clear_warehouse_tool_caches() -> None:
    _load_nutrient_alias_rows.cache_clear()
    _load_column_meaning_rows.cache_clear()


def _parse_match_indices(
    response_text: str, max_index: int, top_k: int
) -> list[int]:
    def add_index(indices: list[int], value: int) -> None:
        if value < 0 or value > max_index:
            return
        if value not in indices:
            indices.append(value)

    indices: list[int] = []
    try:
        payload = json.loads(response_text)
        if isinstance(payload, dict):
            raw = payload.get("match_indices", payload.get("match_index", []))
        else:
            raw = payload
        if isinstance(raw, list):
            for item in raw:
                try:
                    add_index(indices, int(item))
                except (TypeError, ValueError):
                    continue
        else:
            try:
                add_index(indices, int(raw))
            except (TypeError, ValueError):
                pass
    except (json.JSONDecodeError, TypeError, ValueError):
        for match in re.findall(r"-?\d+", response_text):
            try:
                add_index(indices, int(match))
            except ValueError:
                continue

    if not indices:
        return []
    return indices[:top_k]


def _select_best_column_matches(
    query: str, candidates: list[dict], top_k: int
) -> list[dict]:
    if not candidates or top_k <= 0:
        return []
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
            f"Return up to {top_k} best matches.",
            (
                "Return JSON only: "
                "{\"match_indices\": [<0-based indices best-to-worst>]}"
            ),
        ]
    )
    messages = [
        SystemMessage(
            content=(
                "Select the best semantic matches based on column meaning. "
                "Return at most the requested count. If none are relevant, "
                "return an empty list."
            )
        ),
        HumanMessage(content=prompt),
    ]
    response = llm.invoke(messages)
    response_text = response.content if hasattr(response, "content") else str(response)
    match_indices = _parse_match_indices(
        response_text, len(candidates) - 1, top_k
    )
    if not match_indices:
        return []
    return [candidates[index] for index in match_indices]


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
    top_k: int = 5,
) -> list[dict]:
    """Match user-described column meanings to column names using LLM similarity.

    Args:
        query: One or more column-meaning mentions.
        top_k: Max number of matches to return per query.

    Returns:
        A list of results for each query, each with:
        {
          "query": <raw_query>,
          "normalized_query": <normalized_query>,
          "matches": [
            {
              "original_column_name": <column_name>,
              "column_meaning": <meaning>,
              "original_table_name": <table_name>,
              "casual_table_name": <casual_name>
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

    candidates = _load_column_meaning_rows()
    results = []
    for query_entry in normalized_queries:
        query_norm = query_entry["normalized"]
        limited_candidates = _limit_candidates_for_llm(
            query_norm, candidates
        )
        best_matches = _select_best_column_matches(
            query_entry["raw"], limited_candidates, top_k
        )
        match_payload = []
        for match in best_matches:
            match_payload.append(
                {
                    "original_column_name": match[
                        "original_column_name"
                    ],
                    "column_meaning": match["column_meaning"],
                    "original_table_name": match[
                        "original_table_name"
                    ],
                    "casual_table_name": match["casual_table_name"],
                }
            )
        results.append(
            {
                "query": query_entry["raw"],
                "normalized_query": query_norm,
                "matches": match_payload,
            }
        )
    return results


@tool
def query_nutrient_data(
    nutrient_matches: list | str,
    column_matches: list | str,
    spec_num: str,
    change_num: str,
    table_name: str = "SN_MAIVA_Comply_Check_Min_and_Max_As_In_Spec",
    nutrient_column: str = "nutr_name",
    nutrient_key: str | None = None,
    unit_column: str = "unit",
    limit: int = 200,
) -> dict:
    """Query a warehouse table using nutrient and column matches.

    Args:
        nutrient_matches: Output from match_nutrient_names or list of nutrient names.
        column_matches: Output from match_column_names or list of column names.
        spec_num: Specification number to filter (full or shorthand).
        change_num: Change number to filter (full or shorthand).
        table_name: Target table to query (unqualified or qualified).
        nutrient_column: Column used for filtering nutrients.
        nutrient_key: Key to extract from match_nutrient_names output.
            Defaults to nutrient_column.
        unit_column: Column containing the unit for the values.
        limit: Max rows to return.

    Returns:
        {
          "table": <qualified_table_name>,
          "nutrient_column": <nutrient_column>,
          "columns": [<column names>],
          "query": <sql>,
          "rows": [<row values>]
        }
    """
    resolved_nutrient_key = nutrient_key or nutrient_column
    nutrient_values = _extract_nutrient_values(
        nutrient_matches, resolved_nutrient_key
    )
    column_names = _extract_column_names(column_matches)

    if not nutrient_values:
        raise ValueError("No nutrients provided for query.")
    if not column_names:
        raise ValueError("No columns provided for query.")

    nutrient_column_safe = _safe_identifier(nutrient_column)
    unit_column_safe = _safe_identifier(unit_column)
    qualified_table = _qualify_table_name(table_name)

    safe_columns = [_safe_identifier(name) for name in column_names]
    if nutrient_column_safe not in safe_columns:
        safe_columns.insert(0, nutrient_column_safe)
    if unit_column_safe not in safe_columns:
        safe_columns.insert(1, unit_column_safe)

    escaped_values = [
        f"'{_escape_sql_literal(value)}'" for value in nutrient_values
    ]
    in_clause = ", ".join(escaped_values)
    spec_values = _normalize_spec_change(spec_num, SPEC_PREFIX)
    change_values = _normalize_spec_change(change_num, CHANGE_PREFIX)

    if not spec_values:
        raise ValueError("Invalid spec_num; expected at least 4 digits.")
    if not change_values:
        raise ValueError("Invalid change_num; expected at least 4 digits.")

    spec_clause = ", ".join(
        f"'{_escape_sql_literal(value)}'" for value in spec_values
    )
    change_clause = ", ".join(
        f"'{_escape_sql_literal(value)}'" for value in change_values
    )
    limit_clause = ""
    if limit is not None and limit > 0:
        limit_clause = f" LIMIT {int(limit)}"

    sql_statement = (
        f"SELECT {', '.join(safe_columns)} "
        f"FROM {qualified_table} "
        f"WHERE {nutrient_column_safe} IN ({in_clause}) "
        f"AND specification IN ({spec_clause}) "
        f"AND change_number IN ({change_clause})"
        f"{limit_clause}"
    )

    rows = get_data_from_warehouse(sql_statement)
    row_values = [list(row) for row in rows]
    return {
        "table": qualified_table,
        "nutrient_column": nutrient_column_safe,
        "unit_column": unit_column_safe,
        "columns": safe_columns,
        "query": sql_statement,
        "rows": row_values,
    }
