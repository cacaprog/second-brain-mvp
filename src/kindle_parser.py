"""
Parser for Kindle My Clippings.txt file
"""
import re
import uuid
from pathlib import Path
from datetime import datetime
from typing import List
from dateutil import parser as date_parser
from models import Note, SourceType


class KindleParser:
    """Parse Kindle clippings file"""
    
    SEPARATOR = "=========="
    
    @staticmethod
    def parse_file(file_path: Path) -> List[Note]:
        """Parse the entire My Clippings.txt file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Remove BOM if present
        content = content.lstrip('\ufeff')
        
        # Split by separator
        clippings = content.split(KindleParser.SEPARATOR)
        
        notes = []
        for clipping_text in clippings:
            clipping_text = clipping_text.strip()
            if not clipping_text:
                continue
            
            note = KindleParser.parse_clipping(clipping_text)
            if note:
                notes.append(note)
        
        return notes
    
    @staticmethod
    def parse_clipping(clipping_text: str) -> Note:
        """Parse a single clipping"""
        lines = clipping_text.strip().split('\n')
        
        if len(lines) < 3:
            return None
        
        # First line: Book title and author
        title_line = lines[0].strip()
        # Try to extract author from parentheses
        author_match = re.search(r'\(([^)]+)\)$', title_line)
        author = author_match.group(1) if author_match else "Unknown"
        book_title = re.sub(r'\s*\([^)]+\)$', '', title_line).strip()
        
        # Second line: Metadata (position, date)
        metadata_line = lines[1].strip()
        
        # Extract position/location
        position = None
        location_match = re.search(r'posição\s+(\d+-?\d*)', metadata_line, re.IGNORECASE)
        if not location_match:
            location_match = re.search(r'position\s+(\d+-?\d*)', metadata_line, re.IGNORECASE)
        if location_match:
            position = location_match.group(1)
        
        # Extract date
        created_at = None
        # Try Portuguese date format first
        date_patterns = [
            r'Adicionado:\s*(.+?)$',
            r'Added:\s*(.+?)$',
        ]
        for pattern in date_patterns:
            date_match = re.search(pattern, metadata_line, re.IGNORECASE)
            if date_match:
                date_str = date_match.group(1).strip()
                try:
                    created_at = date_parser.parse(date_str, fuzzy=True)
                    break
                except:
                    pass
        
        # Rest of the lines: The actual highlight/note
        content_lines = lines[2:]
        content = '\n'.join(content_lines).strip()
        
        if not content:
            return None
        
        return Note(
            id=str(uuid.uuid4()),
            title=book_title,
            content=content,
            source=SourceType.KINDLE,
            tags=[author],  # Use author as a tag
            created_at=created_at,
            metadata={
                "author": author,
                "position": position,
                "book_title": book_title
            }
        )
    
    @staticmethod
    def parse_directory(directory: Path) -> List[Note]:
        """Parse all .txt files in a directory"""
        notes = []
        for txt_file in directory.glob("**/*.txt"):
            try:
                file_notes = KindleParser.parse_file(txt_file)
                notes.extend(file_notes)
            except Exception as e:
                print(f"Error parsing {txt_file}: {e}")
        return notes
