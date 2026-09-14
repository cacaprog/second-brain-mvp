"""
Parser for Google Drive Obsidian vault backups — v2 NoteRecord.
GDrive exports are Obsidian vaults; all parsing logic lives in obsidian_parser.py.
This module sets source="gdrive" so notes are traceable to their origin.
"""
from pathlib import Path
from typing import List, Optional

from models import NoteRecord
from obsidian_parser import parse_obsidian_file


class GDriveParser:
    @staticmethod
    def parse_to_record(file_path: Path) -> Optional[NoteRecord]:
        return parse_obsidian_file(file_path, source="gdrive")

    @staticmethod
    def parse_directory_to_records(directory: Path) -> List[NoteRecord]:
        records = []
        for md_file in directory.rglob("*.md"):
            try:
                record = parse_obsidian_file(md_file, source="gdrive")
                if record:
                    records.append(record)
            except Exception as e:
                print(f"Error parsing {md_file}: {e}")
        return records
