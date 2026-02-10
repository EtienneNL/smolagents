from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from nat.builder.workflow_builder import WorkflowBuilder
from nat.front_ends.fastapi.fastapi_front_end_plugin_worker import (
    FastApiFrontEndPluginWorker,
)
from nat.runtime.session import SessionManager
from nat.utils.type_utils import override

from .chunking import chunk_pages
from .config import load_vector_search_config
from .text_extractors import extract_text_by_extension
from .vector_search import build_chunk_records, index_documents

logger = logging.getLogger(__name__)


try:
    from nat_mlflow_feedback.fastapi_plugin_worker import (
        MlflowFastAPIPluginWorker as _BaseWorker,
    )
except Exception:
    _BaseWorker = FastApiFrontEndPluginWorker


class DocumentImportResponse(BaseModel):
    document_id: str
    file_name: str
    chunks_indexed: int
    message: str = Field(default="Document indexed successfully.")


class DocumentIngestFastAPIPluginWorker(_BaseWorker):
    """FastAPI plugin worker that adds a document ingestion endpoint."""

    @override
    async def add_routes(self, app: FastAPI, builder: WorkflowBuilder) -> None:
        await super().add_routes(app, builder)
        await self._add_document_import_route(app, builder)

    async def _add_document_import_route(
        self, app: FastAPI, builder: WorkflowBuilder
    ) -> None:
        session_manager = await SessionManager.create(
            config=self._config, shared_builder=builder
        )

        async def import_document(
            request: Request, file: UploadFile = File(...)
        ) -> DocumentImportResponse:
            async with session_manager.session(
                http_connection=request,
                user_authentication_callback=self._http_flow_handler.authenticate,
            ):
                if not file.filename:
                    raise HTTPException(
                        status_code=400, detail="File name is missing."
                    )
                filename = file.filename

                if not filename.lower().endswith((".pdf", ".docx", ".txt")):
                    raise HTTPException(
                        status_code=400,
                        detail="Supported file types: .pdf, .docx, .txt",
                    )

                file_bytes = await file.read()
                if not file_bytes:
                    raise HTTPException(
                        status_code=400, detail="Uploaded file is empty."
                    )

                try:
                    pages = extract_text_by_extension(file_bytes, filename)
                except Exception as exc:
                    logger.exception("Failed to parse uploaded file")
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to parse file: {exc}",
                    ) from exc

                if not pages:
                    raise HTTPException(
                        status_code=400,
                        detail="No extractable text found in file.",
                    )

                config = load_vector_search_config()
                chunks = chunk_pages(
                    pages, config.chunk_size, config.chunk_overlap
                )
                if not chunks:
                    raise HTTPException(
                        status_code=400,
                        detail="Failed to split document into chunks.",
                    )

                doc_id = str(uuid.uuid4())
                chunk_payloads = [
                    {
                        "chunk_index": chunk.chunk_index,
                        "text": chunk.text,
                        "page_number": chunk.page_number,
                    }
                    for chunk in chunks
                ]
                records = build_chunk_records(
                    document_id=doc_id,
                    source=filename,
                    chunks=chunk_payloads,
                    config=config,
                )

                try:
                    result = index_documents(config, documents=records)
                except Exception as exc:
                    logger.exception("Failed to index document in vector search")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to index document: {exc}",
                    ) from exc

                return DocumentImportResponse(
                    document_id=doc_id,
                    file_name=filename,
                    chunks_indexed=result["indexed"],
                )

        app.add_api_route(
            path="/documents/import",
            endpoint=import_document,
            methods=["POST"],
            description="Upload a document (PDF/DOCX/TXT), chunk it, and index in vector search.",
        )
        logger.info("Registered document ingestion endpoint at /documents/import")
