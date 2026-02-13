"""
Minimal FastAPI server for DOCX placeholder filling.

Run:
    uvicorn backend.main:app --reload --port 8001
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

try:
    from backend.docx_processor import analyze_docx_placeholders, fill_docx_template
    from backend.llm_mapper import (
        DEFAULT_LLM_MODEL,
        LLM_AVAILABLE,
        LLM_IMPORT_ERROR,
        extract_scalar_values_with_llm,
    )
except ModuleNotFoundError:
    from docx_processor import analyze_docx_placeholders, fill_docx_template
    from llm_mapper import (
        DEFAULT_LLM_MODEL,
        LLM_AVAILABLE,
        LLM_IMPORT_ERROR,
        extract_scalar_values_with_llm,
    )


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class AnalyzeResponse(BaseModel):
    success: bool
    placeholders: list[str]
    scalar_placeholders: list[str]
    table_placeholders: list[str]
    count: int


class ExtractValuesResponse(BaseModel):
    success: bool
    placeholders: list[str]
    extracted_values: dict[str, str | bool | int | float]
    model: str


app = FastAPI(
    title="DOCX Form Filler (Minimal)",
    version="0.1.0",
    description="Fill placeholder-based DOCX templates with JSON values and Excel table data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_docx(filename: str | None) -> None:
    if not filename or not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="File must be a .docx document")


def _parse_values_json(values: str) -> dict[str, Any]:
    try:
        parsed = json.loads(values) if values else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON for 'values': {exc}") from exc

    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="'values' must be a JSON object")
    return parsed


def _validate_excel_file(excel_file: UploadFile | None) -> bytes | None:
    if excel_file is None:
        return None

    if not excel_file.filename or not excel_file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Excel file must be .xlsx or .xls")

    return None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/analyze-docx", response_model=AnalyzeResponse)
async def analyze_docx(file: UploadFile = File(...)) -> AnalyzeResponse:
    _ensure_docx(file.filename)
    docx_bytes = await file.read()

    try:
        summary = analyze_docx_placeholders(docx_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to analyze DOCX: {exc}") from exc

    return AnalyzeResponse(
        success=True,
        placeholders=summary.all_placeholders,
        scalar_placeholders=summary.scalar_placeholders,
        table_placeholders=summary.table_placeholders,
        count=len(summary.all_placeholders),
    )


@app.post("/fill-docx")
async def fill_docx(
    file: UploadFile = File(...),
    values: str = Form("{}"),
    excel_file: UploadFile | None = File(None),
    use_llm: bool = Form(False),
    instructions: str | None = Form(None),
    anthropic_api_key: str | None = Form(None),
    llm_model: str = Form(DEFAULT_LLM_MODEL),
) -> Response:
    _ensure_docx(file.filename)
    values_dict = _parse_values_json(values)

    docx_bytes = await file.read()
    excel_bytes: bytes | None = None
    if excel_file is not None:
        _validate_excel_file(excel_file)
        excel_bytes = await excel_file.read()

    llm_extracted: dict[str, str | bool | int | float] = {}
    if use_llm:
        if not instructions or not instructions.strip():
            raise HTTPException(status_code=400, detail="'instructions' is required when use_llm=true")
        if not LLM_AVAILABLE:
            raise HTTPException(
                status_code=503,
                detail=f"Anthropic SDK is not available: {LLM_IMPORT_ERROR}. Install with: pip install anthropic",
            )

        try:
            summary = analyze_docx_placeholders(docx_bytes)
            llm_extracted = extract_scalar_values_with_llm(
                instructions=instructions,
                allowed_placeholders=summary.scalar_placeholders,
                model=llm_model,
                api_key=anthropic_api_key,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"LLM extraction failed: {exc}") from exc

        # Explicit user values override LLM-derived values.
        values_dict = {**llm_extracted, **values_dict}

    try:
        filled_bytes = fill_docx_template(docx_bytes, values=values_dict, excel_bytes=excel_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fill DOCX: {exc}") from exc

    output_name = f"{Path(file.filename).stem}_filled.docx"
    headers = {"Content-Disposition": f'attachment; filename="{output_name}"'}
    if use_llm:
        headers["X-LLM-Model"] = llm_model
        headers["X-LLM-Values"] = str(len(llm_extracted))

    return Response(
        content=filled_bytes,
        media_type=DOCX_MIME,
        headers=headers,
    )


@app.post("/extract-values", response_model=ExtractValuesResponse)
async def extract_values(
    file: UploadFile = File(...),
    instructions: str = Form(...),
    anthropic_api_key: str | None = Form(None),
    llm_model: str = Form(DEFAULT_LLM_MODEL),
) -> ExtractValuesResponse:
    _ensure_docx(file.filename)
    if not LLM_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail=f"Anthropic SDK is not available: {LLM_IMPORT_ERROR}. Install with: pip install anthropic",
        )

    docx_bytes = await file.read()
    try:
        summary = analyze_docx_placeholders(docx_bytes)
        values = extract_scalar_values_with_llm(
            instructions=instructions,
            allowed_placeholders=summary.scalar_placeholders,
            model=llm_model,
            api_key=anthropic_api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to extract values: {exc}") from exc

    return ExtractValuesResponse(
        success=True,
        placeholders=summary.scalar_placeholders,
        extracted_values=values,
        model=llm_model,
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "DOCX Form Filler API",
        "analyze_endpoint": "POST /analyze-docx",
        "fill_endpoint": "POST /fill-docx",
        "extract_values_endpoint": "POST /extract-values",
    }
