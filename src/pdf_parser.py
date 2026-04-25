"""
Parser for PDF research papers in data/raw/papers/.
Files in this directory are always treated as article content (note_type="article").
Uses pymupdf (import name: fitz) for local, offline text extraction.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models import NoteRecord, NoteStatus


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _detect_language(text: str) -> str:
    try:
        from langdetect import detect
        lang = detect(text[:500])
        return lang if lang in ("pt", "en", "fr", "es") else "unknown"
    except Exception:
        return "unknown"


def parse(path: Path, db=None) -> Optional[NoteRecord]:
    """Extract text from a PDF and return a NoteRecord, or None if image-only.

    Image-only PDFs (no extractable text) log an error and return None.
    The db parameter is optional — if provided, the error is logged to the errors table.
    """
    import fitz  # pymupdf

    try:
        doc = fitz.open(str(path))
    except Exception as e:
        print(f"[ERROR]  {path.name} — could not open PDF: {e}")
        return None

    pages_text = []
    for page in doc:
        pages_text.append(page.get_text())
    doc.close()

    full_text = "\n".join(pages_text).strip()

    if not full_text:
        msg = f"{path.name} — no extractable text — OCR required"
        print(f"[ERROR]  {msg}")
        if db is not None:
            # Log to errors table with a synthetic note id
            synthetic_id = _sha256(str(path.resolve()))
            try:
                db.log_error(synthetic_id, "parsing", msg)
            except Exception:
                pass
        return None

    body = full_text[:12000]

    # Title: PDF metadata title > filename stem
    try:
        doc2 = fitz.open(str(path))
        raw_title = (doc2.metadata.get("title") or "").strip()
        doc2.close()
    except Exception:
        raw_title = ""
    title = raw_title if raw_title else path.stem

    now = datetime.now(timezone.utc).isoformat()
    language = _detect_language(body)
    word_count = len(body.split())

    return NoteRecord(
        id=_sha256(body),
        title=title,
        body=body,
        tags=[],
        language=language,
        source="papers",
        source_path=str(path.resolve()),
        created_at=now,
        modified_at=now,
        word_count=word_count,
        status=NoteStatus.PENDING,
        note_type="article",
    )
