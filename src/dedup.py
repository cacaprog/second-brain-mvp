"""
Near-duplicate detection for Second Brain v2.
Checks incoming notes against all existing wiki pages via ChromaDB cosine similarity.
A match above DUPLICATE_THRESHOLD triggers a merge proposal instead of new-page creation.
"""
from pathlib import Path
from typing import Optional

import yaml


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def check_duplicate(body: str) -> Optional[str]:
    """
    Embed the note body and query all domain collections.
    Returns the slug of the most similar existing wiki page if similarity >=
    the configured DUPLICATE_THRESHOLD, else None.

    Uses the v2 vector store so only compiled wiki pages are compared
    (raw notes are never indexed).
    """
    from vector_store import get_vector_store

    cfg = _load_settings()
    threshold = cfg["ingestion"]["duplicate_threshold"]
    store = get_vector_store()
    return store.query_similar(body, threshold=threshold)


def build_merge_description(slug: str, new_body: str) -> str:
    """
    Return a short human-readable description of the merge candidate
    for display in the review CLI.
    """
    return (
        f"Potential duplicate of existing page [[{slug}]].\n"
        f"New note preview:\n{new_body[:300]}{'...' if len(new_body) > 300 else ''}"
    )
