"""
Data models for the second brain system (MVP + v2).
"""
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# v2 models — Zettelkasten wiki pipeline
# ---------------------------------------------------------------------------

# NoteRecord status constants
class NoteStatus:
    PENDING = "pending"
    CLASSIFIED = "classified"
    PARSING_FAILED = "parsing_failed"
    MANUAL_QUEUE = "manual_queue"
    DUPLICATE_CANDIDATE = "duplicate_candidate"
    FAST_TRACKED = "fast_tracked"
    COMMITTING = "committing"
    COMMITTED = "committed"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"
    COMMIT_FAILED = "commit_failed"
    DELETED = "deleted"


@dataclass
class NoteRecord:
    """v2 canonical note representation with full lifecycle tracking."""
    id: str                          # SHA-256 of file content
    title: str
    body: str
    tags: List[str]
    language: str                    # pt | en | fr | es | unknown
    source: str                      # notion | keep | kindle
    source_path: str                 # absolute path to raw file
    created_at: str                  # ISO 8601
    modified_at: str                 # ISO 8601
    version: int = 1
    domain: Optional[str] = None
    secondary_domain: Optional[str] = None
    status: str = NoteStatus.PENDING
    wiki_page: Optional[str] = None  # slug of resulting wiki page
    word_count: int = 0
    note_type: Optional[str] = None  # "article" for articles/ and papers/ sources


@dataclass
class Proposal:
    """LLM-generated recommendation for integrating a note into the wiki."""
    id: str                          # UUID4
    note_id: str
    note_version: int
    proposed_page: str               # target wiki page slug
    is_new_page: bool
    link_only: bool
    summary: str                     # 2–3 sentences, same language as note
    proposed_links: List[str]        # existing domain index slugs only
    confidence: float                # 0.0–1.0
    flag_contradiction: bool
    flag_duplicate: bool
    fast_track_eligible: bool
    ollama_model: str
    created_at: str                  # ISO 8601
    decision: Optional[str] = None   # approved | edited | fast_tracked | rejected
    rejection_reason: Optional[str] = None
    decided_at: Optional[str] = None
    edited_content: Optional[str] = None


@dataclass
class CommitRecord:
    """Transaction coordinator entry for atomic wiki commits."""
    id: str                          # UUID4
    proposal_id: str
    status: str                      # committing | committed | failed
    started_at: str                  # ISO 8601
    git_hash: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ErrorRecord:
    """Dead-letter queue entry for pipeline failures."""
    id: str                          # UUID4
    note_id: str
    stage: str                       # parsing | classifying | proposing | committing
    error_message: str
    occurred_at: str                 # ISO 8601
    resolved: int = 0                # 0 | 1


@dataclass
class IngestJob:
    """Work item queued by the file watcher."""
    path: str
    event: str                       # create | modify | delete


@dataclass
class DomainConfig:
    """Runtime domain configuration loaded from domains.yaml."""
    name: str
    seeds: List[str]
    max_pages: int = 300
    centroid_embedding: Optional[object] = None  # np.ndarray, set after precompute
