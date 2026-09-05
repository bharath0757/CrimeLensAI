"""Bounded document-to-text conversion; offsets reference the returned text."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from app.core.config import settings

MAX_TEXT_CHARACTERS = 500_000
MAX_PAGES = 200


class DocumentTextError(ValueError):
    """The uploaded document cannot be safely processed as text."""


@dataclass(frozen=True)
class DocumentText:
    text: str
    sha256: str


def read_document(file_path: str) -> DocumentText:
    root = Path(settings.UPLOAD_DIR).resolve()
    path = Path(file_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise DocumentTextError("Document is not in the configured evidence directory.")
    if path.stat().st_size > settings.MAX_FILE_SIZE_BYTES:
        raise DocumentTextError("Document exceeds the upload size limit.")
    return decode_document(path.read_bytes(), path.suffix.lower())


def decode_document(raw: bytes, suffix: str) -> DocumentText:
    """Convert bounded uploaded bytes, without persisting a preview on disk."""
    if len(raw) > settings.MAX_FILE_SIZE_BYTES:
        raise DocumentTextError("Document exceeds the upload size limit.")
    suffix = suffix.lower()
    if suffix in {".txt", ".csv", ".json", ".log"}:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DocumentTextError("Text files must use UTF-8 encoding.") from exc
    elif suffix == ".pdf":
        if not raw.startswith(b"%PDF-"):
            raise DocumentTextError("PDF could not be read: invalid file signature.")
        from io import BytesIO

        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(BytesIO(raw))
            if reader.is_encrypted:
                raise DocumentTextError("Encrypted PDFs must be decrypted before upload.")
            if len(reader.pages) > MAX_PAGES:
                raise DocumentTextError("PDF exceeds the 200-page processing limit.")
            parts = []
            for page in reader.pages:
                parts.append(page.extract_text() or "")
                if sum(map(len, parts)) > MAX_TEXT_CHARACTERS:
                    raise DocumentTextError("Extracted text exceeds 500,000 characters.")
            text = "\n\f\n".join(parts)
        except PdfReadError as exc:
            raise DocumentTextError("PDF could not be read.") from exc
    elif suffix == ".docx":
        from io import BytesIO

        from docx import Document

        try:
            with ZipFile(BytesIO(raw)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 50_000_000:
                    raise DocumentTextError("Expanded DOCX exceeds the processing limit.")
            document = Document(BytesIO(raw))
            parts = []
            for block in document.iter_inner_content():
                if hasattr(block, "text"):
                    parts.append(block.text)
                else:
                    parts.extend("\t".join(cell.text for cell in row.cells) for row in block.rows)
            text = "\n".join(parts)
        except (BadZipFile, KeyError) as exc:
            raise DocumentTextError("DOCX could not be read.") from exc
    else:
        raise DocumentTextError("Text extraction supports TXT, PDF, DOCX, CSV, JSON and LOG. Images require OCR.")
    if not text.strip():
        raise DocumentTextError("No readable text found. Scanned documents require OCR before extraction.")
    if len(text) > MAX_TEXT_CHARACTERS:
        raise DocumentTextError("Extracted text exceeds 500,000 characters.")
    return DocumentText(text=text, sha256=hashlib.sha256(raw).hexdigest())
