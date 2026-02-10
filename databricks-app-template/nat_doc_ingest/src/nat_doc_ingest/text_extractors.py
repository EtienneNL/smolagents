from __future__ import annotations

from dataclasses import dataclass
import io

from docx import Document
from pypdf import PdfReader


@dataclass(frozen=True)
class PageText:
    page_number: int | None
    text: str


def extract_pdf_text(file_bytes: bytes) -> list[PageText]:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages: list[PageText] = []
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        cleaned = text.strip()
        if cleaned:
            pages.append(PageText(page_number=idx + 1, text=cleaned))
    return pages


def extract_docx_text(file_bytes: bytes) -> list[PageText]:
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
    if not paragraphs:
        return []
    return [PageText(page_number=None, text="\n".join(paragraphs))]


def extract_txt_text(file_bytes: bytes) -> list[PageText]:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            decoded = file_bytes.decode(encoding)
            cleaned = decoded.strip()
            if cleaned:
                return [PageText(page_number=None, text=cleaned)]
            return []
        except UnicodeDecodeError:
            continue
    raise ValueError("Unsupported text encoding for .txt file.")


def extract_text_by_extension(file_bytes: bytes, filename: str) -> list[PageText]:
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension == "pdf":
        return extract_pdf_text(file_bytes)
    if extension == "docx":
        return extract_docx_text(file_bytes)
    if extension == "txt":
        return extract_txt_text(file_bytes)
    raise ValueError(f"Unsupported file extension: .{extension}")
