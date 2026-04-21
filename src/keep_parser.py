"""
Parser for Google Keep exports (HTML and JSON)
"""
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from bs4 import BeautifulSoup
from models import Note, SourceType


class KeepParser:
    """Parse Google Keep exports"""
    
    @staticmethod
    def parse_json(json_path: Path) -> Optional[Note]:
        """Parse a Google Keep JSON file"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract basic info
            title = data.get('title', '')
            content = data.get('textContent', '')
            
            # Get labels (tags)
            labels = data.get('labels', [])
            tags = [label.get('name', '') for label in labels if label.get('name')]
            
            # Get timestamps
            created_timestamp = data.get('createdTimestampUsec', 0)
            created_at = None
            if created_timestamp:
                created_at = datetime.fromtimestamp(created_timestamp / 1_000_000)
            
            # Get annotations (links, etc)
            annotations = data.get('annotations', [])
            annotation_urls = [ann.get('url') for ann in annotations if ann.get('url')]
            
            # Get color
            color = data.get('color', 'DEFAULT')
            
            # Check if archived, trashed, or pinned
            is_archived = data.get('isArchived', False)
            is_trashed = data.get('isTrashed', False)
            is_pinned = data.get('isPinned', False)
            
            return Note(
                id=str(uuid.uuid4()),
                title=title or "Untitled Keep Note",
                content=content,
                source=SourceType.KEEP,
                tags=tags,
                created_at=created_at,
                metadata={
                    "file_path": str(json_path),
                    "color": color,
                    "is_archived": is_archived,
                    "is_trashed": is_trashed,
                    "is_pinned": is_pinned,
                    "annotation_urls": annotation_urls
                }
            )
        except Exception as e:
            print(f"Error parsing {json_path}: {e}")
            return None
    
    @staticmethod
    def parse_directory(directory: Path) -> List[Note]:
        """Parse all JSON files in a directory"""
        notes = []
        for json_file in directory.glob("**/*.json"):
            note = KeepParser.parse_json(json_file)
            if note and not note.metadata.get('is_trashed', False):
                notes.append(note)
        return notes
