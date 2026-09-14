"""
Parser for Obsidian Web Clipper markdown files in data/raw/articles/.
Files in this directory are always treated as article content (note_type="article").
"""
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from models import NoteRecord, NoteStatus


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _detect_language(text: str) -> str:
    try:
        from langdetect import detect, LangDetectException
        lang = detect(text[:500])
        return lang if lang in ("pt", "en", "fr", "es") else "unknown"
    except Exception:
        return "unknown"


def _split_front_matter(content: str) -> tuple[dict, str]:
    """Split YAML front matter from body. Returns (meta_dict, body_text)."""
    if not content.startswith("---"):
        return {}, content
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
    if not match:
        return {}, content
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, match.group(2)


def extract_source_url(path: Path) -> Optional[str]:
    """Extract the url: field from an Obsidian Web Clipper markdown front matter."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        meta, _ = _split_front_matter(content)
        url = str(meta.get("url", "")).strip()
        return url if url else None
    except OSError:
        return None


def parse(path: Path) -> Optional[NoteRecord]:
    """Parse an Obsidian Web Clipper markdown file into a NoteRecord.

    Returns None if the file body is empty after stripping.
    """
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    meta, body_raw = _split_front_matter(content)

    # Title: YAML title > first H1 > filename stem
    title = str(meta.get("title", "")).strip()
    if not title:
        h1 = re.search(r"^#\s+(.+)$", body_raw, re.MULTILINE)
        title = h1.group(1).strip() if h1 else path.stem

    body = body_raw.strip()[:12000]

    if not body:
        print(f"[SKIP]   {path.name} — empty body, skipped")
        return None

    source_url = str(meta.get("url", "")).strip() or None
    tags_raw = meta.get("tags", [])
    tags = [str(t) for t in (tags_raw if isinstance(tags_raw, list) else [tags_raw])]
    if source_url:
        tags.append(f"url:{source_url}")

    now = datetime.now(timezone.utc).isoformat()
    language = _detect_language(body)
    word_count = len(body.split())

    return NoteRecord(
        id=_sha256(body),
        title=title,
        body=body,
        tags=tags,
        language=language,
        source="articles",
        source_path=str(path.resolve()),
        created_at=now,
        modified_at=now,
        word_count=word_count,
        status=NoteStatus.PENDING,
        note_type="article",
    )
