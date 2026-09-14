"""
Parser for Evernote HTML exports — v2 NoteRecord.
Each .html file is one Evernote note. Metadata is in <meta itemprop="..."> tags.
Body text is extracted from the <en-note> element (or <body> as fallback).
"""
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from bs4 import BeautifulSoup

from models import NoteRecord


def _is_attachment_dir(file_path: Path) -> bool:
    return any(
        part.endswith(" files") or part.endswith("_files")
        for part in file_path.parts
    )


def _parse_evernote_date(date_str: Optional[str]) -> Optional[str]:
    """Parse Evernote ISO-compact format '20220704T221453Z' → ISO 8601."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


class EvernoteParser:
    @staticmethod
    def parse_to_record(html_path: Path) -> Optional[NoteRecord]:
        from langdetect import detect, DetectorFactory
        DetectorFactory.seed = 0

        if html_path.name.startswith("."):
            return None
        if _is_attachment_dir(html_path):
            return None

        raw_bytes = html_path.read_bytes()
        # Evernote HTML files can have binary attachment preamble — decode leniently
        try:
            content = raw_bytes.decode("utf-8", errors="replace")
        except Exception:
            return None

        # Skip macOS resource fork files (binary content, not valid HTML)
        if not content.lstrip().startswith("<!"):
            return None

        note_id = hashlib.sha256(raw_bytes).hexdigest()
        soup = BeautifulSoup(content, "lxml")

        def _meta(prop: str) -> Optional[str]:
            tag = soup.find("meta", attrs={"itemprop": prop})
            return tag.get("content") if tag else None

        title = _meta("title") or html_path.stem
        created_at = (
            _parse_evernote_date(_meta("created"))
            or datetime.fromtimestamp(html_path.stat().st_ctime, tz=timezone.utc).isoformat()
        )
        modified_at = _parse_evernote_date(_meta("updated")) or created_at

        # Body: prefer <en-note>, fall back to <body>
        body_tag = soup.find("en-note") or soup.find("body")
        body = body_tag.get_text(separator="\n", strip=True) if body_tag else ""

        # Strip leading title repetition (Evernote sometimes renders title in body)
        body = re.sub(r"^\s*" + re.escape(title) + r"\s*\n?", "", body).strip()

        # Tags: Evernote HTML encodes them as <li data-target="tag-name">
        tags = [
            t.get_text(strip=True)
            for t in soup.find_all(attrs={"data-target": "tag-name"})
            if t.get_text(strip=True)
        ]

        word_count = len(body.split())

        try:
            lang = detect(body[:500]) if body else "unknown"
            if lang not in ("pt", "en", "fr", "es"):
                lang = "unknown"
        except Exception:
            lang = "unknown"

        return NoteRecord(
            id=note_id,
            title=title,
            body=body,
            tags=tags,
            language=lang,
            source="evernote",
            source_path=str(html_path.resolve()),
            created_at=created_at,
            modified_at=modified_at,
            word_count=word_count,
        )

    @staticmethod
    def parse_directory_to_records(directory: Path) -> List[NoteRecord]:
        records = []
        for html_file in directory.rglob("*.html"):
            try:
                record = EvernoteParser.parse_to_record(html_file)
                if record:
                    records.append(record)
            except Exception as e:
                print(f"Error parsing {html_file}: {e}")
        return records
