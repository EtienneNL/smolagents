"""
Optional LLM-based value extraction for DOCX placeholders.

This module is intentionally isolated:
- Filling remains deterministic in docx_processor.py
- LLM is used only to convert free-text instructions -> typed placeholder values
"""

from __future__ import annotations

import os
from typing import Union

from pydantic import BaseModel, Field

try:
    import anthropic

    LLM_AVAILABLE = True
    LLM_IMPORT_ERROR = None
except ImportError as exc:
    anthropic = None
    LLM_AVAILABLE = False
    LLM_IMPORT_ERROR = str(exc)


DEFAULT_LLM_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")

ScalarValue = Union[str, bool, int, float]


class ScalarFillPlan(BaseModel):
    """Structured output for scalar placeholder extraction."""

    values: dict[str, ScalarValue] = Field(
        default_factory=dict,
        description="Mapping of placeholder key to value. Keys must be from the allowed placeholder list.",
    )


def extract_scalar_values_with_llm(
    instructions: str,
    allowed_placeholders: list[str],
    *,
    model: str = DEFAULT_LLM_MODEL,
    api_key: str | None = None,
) -> dict[str, ScalarValue]:
    """
    Extract typed scalar values from free-text instructions using structured outputs.

    Post-validation enforces allowed keys so downstream filling stays deterministic.
    """
    if not allowed_placeholders:
        return {}

    if not LLM_AVAILABLE:
        raise ValueError(
            f"Anthropic SDK is not available: {LLM_IMPORT_ERROR}. "
            "Install with: pip install anthropic"
        )

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError(
            "Anthropic API key is required for LLM extraction. "
            "Pass anthropic_api_key or set ANTHROPIC_API_KEY."
        )

    normalized_allowed = sorted({_normalize_key(k) for k in allowed_placeholders if _normalize_key(k)})
    if not normalized_allowed:
        return {}

    prompt = f"""You extract values for DOCX placeholders from user instructions.

Allowed scalar placeholders (ONLY use these keys):
{normalized_allowed}

User instructions:
{instructions}

Rules:
- Return ONLY keys from the allowed list.
- Omit keys that are not specified.
- Keep values concise and typed correctly (string/boolean/int/float).
- Do not include table placeholders.
"""

    client = anthropic.Anthropic(api_key=key)
    response = client.beta.messages.parse(
        model=model,
        max_tokens=1024,
        temperature=0,
        betas=["structured-outputs-2025-11-13"],
        messages=[{"role": "user", "content": prompt}],
        output_format=ScalarFillPlan,
    )

    parsed: ScalarFillPlan = response.parsed_output
    allowed_set = set(normalized_allowed)
    cleaned: dict[str, ScalarValue] = {}

    for raw_key, value in parsed.values.items():
        key_norm = _normalize_key(raw_key)
        if key_norm in allowed_set:
            cleaned[key_norm] = value

    return cleaned


def _normalize_key(key: str) -> str:
    key = str(key).strip()
    if key.startswith("{{") and key.endswith("}}"):
        key = key[2:-2].strip()
    return key
