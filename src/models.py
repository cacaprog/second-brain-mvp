"""
Data models for the second brain system
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from enum import Enum


class SourceType(Enum):
    NOTION = "notion"
    KEEP = "keep"
    KINDLE = "kindle"


@dataclass
class Note:
    """Represents a single note from any source"""
    id: str
    title: str
    content: str
    source: SourceType
    tags: List[str]
    created_at: Optional[datetime]
    metadata: dict
    language: Optional[str] = None
    
    def __post_init__(self):
        """Ensure tags is always a list"""
        if self.tags is None:
            self.tags = []
        if not isinstance(self.tags, list):
            self.tags = [self.tags]
    
    def to_dict(self):
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source.value,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
            "language": self.language
        }
    
    def get_full_text(self) -> str:
        """Get combined title and content for embedding"""
        return f"{self.title}\n\n{self.content}".strip()
