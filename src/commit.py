"""
SQLite-coordinated atomic commit layer for Second Brain v2.
Executes all 7 commit steps in order; all steps 1-6 are idempotent.
On startup, replays any commits stuck in status='committing'.
"""
from pathlib import Path

import yaml

from models import NoteRecord, NoteStatus, Proposal


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def commit(proposal: Proposal, note: NoteRecord) -> None:
    """
    Execute all 7 commit steps atomically.
    Steps 1-6 are idempotent; step 7 (finish_commit) is the only non-idempotent step
    and is always last.
    """
    from db import get_db
    import wiki_store
    from vector_store import get_vector_store

    db = get_db()

    # Step 1 — begin commit (status = 'committing')
    commit_id = db.begin_commit(proposal.id)

    try:
        # Resolve content: article knowledge cards use their own renderer
        if note.note_type in ("article", "rich_note"):
            source_url = None
            if note.source in ("articles",):
                from article_parser import extract_source_url
                source_url = extract_source_url(Path(note.source_path))
            content = wiki_store.render_knowledge_card_page(
                existing_content=wiki_store.read_wiki_page(note.domain or "personal", proposal.proposed_page),
                slug=proposal.proposed_page,
                domain=note.domain or "personal",
                body=proposal.edited_content or proposal.summary,
                source_path=note.source_path,
                links=proposal.proposed_links,
                languages=[note.language] if note.language != "unknown" else [],
                confidence=proposal.confidence,
                source_url=source_url,
                edited_content=None,
                note_type=note.note_type,
            )
        else:
            content = wiki_store.render_wiki_page(
                existing_content=wiki_store.read_wiki_page(note.domain or "personal", proposal.proposed_page),
                slug=proposal.proposed_page,
                domain=note.domain or "personal",
                summary=proposal.summary,
                source_path=note.source_path,
                links=proposal.proposed_links,
                languages=[note.language] if note.language != "unknown" else [],
                confidence=proposal.confidence,
                edited_content=proposal.edited_content,
            )

        # Step 2 — write wiki page (idempotent)
        page_path = wiki_store.write_wiki_page(
            note.domain or "personal",
            proposal.proposed_page,
            content,
        )

        # Step 3 — upsert ChromaDB (idempotent by slug)
        store = get_vector_store()
        store.upsert(
            slug=proposal.proposed_page,
            content=content,
            domain=note.domain or "personal",
            language=note.language,
        )

        # Step 4 — register cross-links (idempotent)
        for link in proposal.proposed_links:
            wiki_store.register_cross_link(
                source=proposal.proposed_page,
                target=link,
            )

        # Step 5 — update domain index (idempotent)
        wiki_store.update_domain_index(
            domain=note.domain or "personal",
            slug=proposal.proposed_page,
            description=proposal.summary[:80],
            languages=[note.language] if note.language != "unknown" else [],
        )

        # Step 6 — git commit (produces git_hash)
        git_hash = wiki_store.git_commit_wiki(
            page_path=page_path,
            slug=proposal.proposed_page,
            confidence=proposal.confidence,
            model=proposal.ollama_model,
        )

        # Step 7 — finish commit (the only non-idempotent step, always last)
        db.finish_commit(commit_id, git_hash=git_hash)
        db.set_note_status(note.id, NoteStatus.COMMITTED, wiki_page=proposal.proposed_page)

        print(
            f"[COMMIT] {proposal.proposed_page} committed "
            f"(git={git_hash[:8]}, conf={proposal.confidence:.2f})"
        )

    except Exception as e:
        db.fail_commit(commit_id, str(e))
        db.log_error(note.id, "committing", str(e))
        raise


def revert_commit(proposal_id: str) -> None:
    """
    Retroactively revert a committed proposal via git revert.
    Used for fast-track retroactive rejection from batch log review.
    """
    from db import get_db
    import wiki_store

    db = get_db()
    git_hash = db.get_commit_git_hash(proposal_id)
    if not git_hash:
        raise ValueError(f"No committed git hash found for proposal {proposal_id}")

    wiki_store.revert_wiki_commit(git_hash)
    print(f"[REVERT] Reverted commit {git_hash[:8]} for proposal {proposal_id}")


def replay_unfinished_commits() -> None:
    """
    On startup: replay all commits stuck in status='committing'.
    All commit steps are idempotent so replaying is always safe.
    """
    from db import get_db

    db = get_db()
    stuck = db.get_commits_by_status("committing")
    if not stuck:
        return

    print(f"[REPLAY] Found {len(stuck)} unfinished commit(s) — replaying...")
    for commit_record in stuck:
        proposal = db.get_proposal(commit_record.proposal_id)
        if not proposal:
            print(f"[REPLAY] WARNING: proposal {commit_record.proposal_id} not found, skipping")
            continue
        note = db.get_note(proposal.note_id)
        if not note:
            print(f"[REPLAY] WARNING: note {proposal.note_id} not found, skipping")
            continue
        try:
            commit(proposal, note)
            print(f"[REPLAY] OK: {proposal.proposed_page}")
        except Exception as e:
            print(f"[REPLAY] FAILED: {proposal.proposed_page}: {e}")
