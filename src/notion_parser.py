"""
Parser for Notion markdown exports
"""
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import List
from models import Note, SourceType


class NotionParser:
    """Parse Notion markdown exports"""
    
    @staticmethod
    def parse_file(file_path: Path) -> Note:
        """Parse a single Notion markdown file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract title (first # heading)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1) if title_match else file_path.stem
        
        # Extract tags
        tags = []
        tag_match = re.search(r'^Tag:\s*(.+)$', content, re.MULTILINE)
        if tag_match:
            tag_text = tag_match.group(1)
            tags = [t.strip() for t in tag_text.split(',')]
        
        # Extract source URL if present
        source_url = None
        source_match = re.search(r'^Source:\s*(.+)$', content, re.MULTILINE)
        if source_match:
            source_url = source_match.group(1)
        
        # Extract type if present
        note_type = None
        type_match = re.search(r'^Type:\s*(.+)$', content, re.MULTILINE)
        if type_match:
            note_type = type_match.group(1)
        
        # Remove metadata lines from content
        clean_content = re.sub(r'^(#\s+.+|Tag:.+|Source:.+|Type:.+)\n?', '', content, flags=re.MULTILINE)
        clean_content = clean_content.strip()
        
        # Try to get creation date from file stats
        try:
            created_at = datetime.fromtimestamp(file_path.stat().st_ctime)
        except:
            created_at = None
        
        return Note(
            id=str(uuid.uuid4()),
            title=title,
            content=clean_content,
            source=SourceType.NOTION,
            tags=tags,
            created_at=created_at,
            metadata={
                "file_path": str(file_path),
                "source_url": source_url,
                "type": note_type
            }
        )
    
    @staticmethod
    def parse_directory(directory: Path) -> List[Note]:
        """Parse all markdown files in a directory"""
        notes = []
        for md_file in directory.glob("**/*.md"):
            try:
                note = NotionParser.parse_file(md_file)
                notes.append(note)
            except Exception as e:
                print(f"Error parsing {md_file}: {e}")
        return notes
