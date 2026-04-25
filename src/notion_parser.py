"""
Parser for Notion markdown exports.
"""
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from models import NoteRecord


class NotionParser:
    """Parse Notion markdown exports into NoteRecords."""

    @staticmethod
    def parse_to_record(file_path: Path) -> NoteRecord:
        """Parse a Notion markdown file into a v2 NoteRecord."""
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0

        raw_bytes = file_path.read_bytes()
        content = raw_bytes.decode("utf-8")
        note_id = hashlib.sha256(raw_bytes).hexdigest()

        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else file_path.stem

        tags = []
        tag_match = re.search(r"^Tag:\s*(.+)$", content, re.MULTILINE)
        if tag_match:
            tags = [t.strip() for t in tag_match.group(1).split(",")]

        hash_tags = re.findall(r"(?<!\[)#(\w+)", content)
        tags = list(dict.fromkeys(tags + hash_tags))

        body = re.sub(r"^(#\s+.+|Tag:.+|Source:.+|Type:.+)\n?", "", content, flags=re.MULTILINE).strip()
        word_count = len(body.split())

        try:
            lang = detect(body[:500]) if body else "unknown"
            if lang not in ("pt", "en", "fr", "es"):
                lang = "unknown"
        except Exception:
            lang = "unknown"

        stat = file_path.stat()
        created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc).isoformat()
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        return NoteRecord(
            id=note_id,
            title=title,
            body=body,
            tags=tags,
            language=lang,
            source="notion",
            source_path=str(file_path.resolve()),
            created_at=created_at,
            modified_at=modified_at,
            word_count=word_count,
        )

    @staticmethod
    def parse_directory_to_records(directory: Path) -> List[NoteRecord]:
        """Parse all markdown files in a directory to NoteRecords."""
        records = []
        for md_file in directory.glob("**/*.md"):
            try:
                records.append(NotionParser.parse_to_record(md_file))
            except Exception as e:
                print(f"Error parsing {md_file}: {e}")
        return records
