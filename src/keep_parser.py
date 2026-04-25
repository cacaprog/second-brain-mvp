"""
Parser for Google Keep JSON exports.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from models import NoteRecord


class KeepParser:
    """Parse Google Keep JSON exports into NoteRecords."""

    @staticmethod
    def parse_to_record(json_path: Path) -> Optional[NoteRecord]:
        """Parse a Google Keep JSON file into a v2 NoteRecord."""
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0

        try:
            raw_bytes = json_path.read_bytes()
            data = json.loads(raw_bytes)
        except Exception:
            return None

        if data.get("isTrashed", False):
            return None

        note_id = hashlib.sha256(raw_bytes).hexdigest()
        title = data.get("title", "") or "Untitled Keep Note"
        body = data.get("textContent", "") or ""
        labels = data.get("labels", [])
        tags = [lbl.get("name", "") for lbl in labels if lbl.get("name")]
        word_count = len(body.split())

        try:
            lang = detect(body[:500]) if body else "unknown"
            if lang not in ("pt", "en", "fr", "es"):
                lang = "unknown"
        except Exception:
            lang = "unknown"

        created_ts = data.get("createdTimestampUsec", 0)
        edited_ts = data.get("userEditedTimestampUsec", created_ts)
        created_at = datetime.fromtimestamp(created_ts / 1_000_000, tz=timezone.utc).isoformat() if created_ts else datetime.now(timezone.utc).isoformat()
        modified_at = datetime.fromtimestamp(edited_ts / 1_000_000, tz=timezone.utc).isoformat() if edited_ts else created_at

        return NoteRecord(
            id=note_id,
            title=title,
            body=body,
            tags=tags,
            language=lang,
            source="keep",
            source_path=str(json_path.resolve()),
            created_at=created_at,
            modified_at=modified_at,
            word_count=word_count,
        )

    @staticmethod
    def parse_directory_to_records(directory: Path) -> List[NoteRecord]:
        """Parse all Keep JSON files in a directory to NoteRecords (skip trashed)."""
        records = []
        for json_file in directory.glob("**/*.json"):
            record = KeepParser.parse_to_record(json_file)
            if record:
                records.append(record)
        return records
