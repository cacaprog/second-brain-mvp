"""
Parser for Obsidian markdown vaults — supports v2 NoteRecord.
Shared core logic (parse_obsidian_file) is also used by gdrive_parser.py
since GDrive exports are Obsidian vault backups.
"""
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from models import NoteRecord


def _parse_yaml_frontmatter(content: str) -> tuple[dict, str]:
    """Return (metadata_dict, body_without_frontmatter)."""
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content
    fm_text = content[3:end].strip()
    body = content[end + 4:].strip()
    try:
        import yaml
        meta = yaml.safe_load(fm_text) or {}
    except Exception:
        meta = {}
    return meta, body


def _strip_obsidian_syntax(text: str) -> str:
    text = re.sub(r"!\[\[[^\]]+\]\]", "", text)                     # ![[embed]] → removed
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)       # [[Page|alias]] → alias
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)                 # [[Page]] → Page
    return text


def _extract_hashtags(text: str) -> list[str]:
    no_code = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    no_code = re.sub(r"`[^`]+`", "", no_code)
    return re.findall(r"(?<!\[)#(\w+)", no_code)


def _is_excalidraw(content: str) -> bool:
    return "excalidraw-plugin:" in content[:300]


def _is_obsidian_config(file_path: Path) -> bool:
    return ".obsidian" in file_path.parts


def _is_attachment_dir(file_path: Path) -> bool:
    return any(
        part.endswith("_files") or part.endswith(" files") or part == "_resources"
        for part in file_path.parts
    )


def _parse_timestamp(val) -> Optional[str]:
    if not val:
        return None
    if isinstance(val, datetime):
        return val.astimezone(timezone.utc).isoformat()
    try:
        from dateutil import parser as dp
        return dp.parse(str(val)).astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def parse_obsidian_file(file_path: Path, source: str = "obsidian") -> Optional[NoteRecord]:
    """
    Parse any Obsidian-format markdown file into a NoteRecord.
    source can be "obsidian" or "gdrive" (vault backup).
    Returns None for config files, attachment dirs, Excalidraw files, and hidden files.
    """
    from langdetect import detect, DetectorFactory
    DetectorFactory.seed = 0

    if file_path.name.startswith("."):
        return None
    if _is_obsidian_config(file_path):
        return None
    if _is_attachment_dir(file_path):
        return None

    raw_bytes = file_path.read_bytes()
    content = raw_bytes.decode("utf-8", errors="replace")

    if _is_excalidraw(content):
        return None

    note_id = hashlib.sha256(raw_bytes).hexdigest()
    meta, body = _parse_yaml_frontmatter(content)

    # Title: frontmatter → first H1 → filename stem
    h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    title = (
        str(meta.get("title", "")).strip()
        or (h1_match.group(1).strip() if h1_match else "")
        or file_path.stem
    )

    # Tags: frontmatter + #hashtags in body
    fm_tags = meta.get("tags") or []
    if isinstance(fm_tags, str):
        fm_tags = [t.strip() for t in fm_tags.split(",")]
    hash_tags = _extract_hashtags(body)
    tags = list(dict.fromkeys([str(t) for t in fm_tags] + hash_tags))

    body = _strip_obsidian_syntax(body)
    body = re.sub(r"^#\s+.+\n?", "", body, count=1, flags=re.MULTILINE).strip()
    word_count = len(body.split())

    try:
        lang = detect(body[:500]) if body else "unknown"
        if lang not in ("pt", "en", "fr", "es"):
            lang = "unknown"
    except Exception:
        lang = "unknown"

    stat = file_path.stat()
    created_at = (
        _parse_timestamp(meta.get("created") or meta.get("date"))
        or datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
    )
    modified_at = (
        _parse_timestamp(meta.get("updated") or meta.get("modified"))
        or datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    )

    return NoteRecord(
        id=note_id,
        title=title,
        body=body,
        tags=tags,
        language=lang,
        source=source,
        source_path=str(file_path.resolve()),
        created_at=created_at,
        modified_at=modified_at,
        word_count=word_count,
    )


class ObsidianParser:
    @staticmethod
    def parse_to_record(file_path: Path) -> Optional[NoteRecord]:
        return parse_obsidian_file(file_path, source="obsidian")

    @staticmethod
    def parse_directory_to_records(directory: Path) -> List[NoteRecord]:
        records = []
        for md_file in directory.rglob("*.md"):
            try:
                record = parse_obsidian_file(md_file, source="obsidian")
                if record:
                    records.append(record)
            except Exception as e:
                print(f"Error parsing {md_file}: {e}")
        return records
