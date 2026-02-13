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
except ModuleNotFoundError:
    from docx_processor import analyze_docx_placeholders, fill_docx_template


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class AnalyzeResponse(BaseModel):
    success: bool
    placeholders: list[str]
    scalar_placeholders: list[str]
    table_placeholders: list[str]
    count: int


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
) -> Response:
    _ensure_docx(file.filename)
    values_dict = _parse_values_json(values)

    excel_bytes: bytes | None = None
    if excel_file is not None:
        if not excel_file.filename or not excel_file.filename.lower().endswith((".xlsx", ".xls")):
            raise HTTPException(status_code=400, detail="Excel file must be .xlsx or .xls")
        excel_bytes = await excel_file.read()

    docx_bytes = await file.read()

    try:
        filled_bytes = fill_docx_template(docx_bytes, values=values_dict, excel_bytes=excel_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fill DOCX: {exc}") from exc

    output_name = f"{Path(file.filename).stem}_filled.docx"
    return Response(
        content=filled_bytes,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "message": "DOCX Form Filler API",
        "analyze_endpoint": "POST /analyze-docx",
        "fill_endpoint": "POST /fill-docx",
    }
