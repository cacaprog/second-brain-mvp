"""
File watcher and ingestion pipeline orchestrator for Second Brain v2.
Monitors data/raw/ for file changes and drives notes through:
  parse → dedup → classify → propose → route (fast-track or pending queue)

Usage:
  python src/watcher.py              # Start daemon
  python src/watcher.py --once PATH  # Process a single file without daemon
  python src/watcher.py --replay     # Replay unfinished commits only
"""
import json
import queue
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from models import IngestJob, NoteRecord, NoteStatus


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


_ingest_queue: queue.Queue = queue.Queue()
_last_modified: dict[str, float] = {}


# ---------------------------------------------------------------------------
# File watcher
# ---------------------------------------------------------------------------

class RawSourceHandler(FileSystemEventHandler):
    def __init__(self, debounce: float = 1.0):
        self.debounce = debounce

    def on_created(self, event):
        if not event.is_directory:
            _ingest_queue.put(IngestJob(path=event.src_path, event="create"))

    def on_modified(self, event):
        if event.is_directory:
            return
        now = time.time()
        if now - _last_modified.get(event.src_path, 0) < self.debounce:
            return
        _last_modified[event.src_path] = now
        _ingest_queue.put(IngestJob(path=event.src_path, event="modify"))

    def on_deleted(self, event):
        if not event.is_directory:
            _ingest_queue.put(IngestJob(path=event.src_path, event="delete"))


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_note(file_path: Path) -> list[NoteRecord]:
    """Parse a raw file into NoteRecords based on its parent directory."""
    parts = file_path.parts
    source = None
    for part in parts:
        if part in ("notion", "keep", "kindle", "evernote", "gdrive", "obsidian",
                    "articles", "papers"):
            source = part
            break

    if source == "articles" and file_path.suffix == ".md":
        from article_parser import parse as parse_article
        record = parse_article(file_path)
        return [record] if record else []
    elif source == "papers" and file_path.suffix == ".pdf":
        from pdf_parser import parse as parse_pdf
        record = parse_pdf(file_path)
        return [record] if record else []
    elif source == "notion" and file_path.suffix == ".md":
        from notion_parser import NotionParser
        record = NotionParser.parse_to_record(file_path)
        return [record] if record else []
    elif source == "keep" and file_path.suffix == ".json":
        from keep_parser import KeepParser
        record = KeepParser.parse_to_record(file_path)
        return [record] if record else []
    elif source == "kindle" and file_path.suffix == ".txt":
        from kindle_parser import KindleParser
        return KindleParser.parse_to_records(file_path)
    elif source == "gdrive" and file_path.suffix == ".md":
        from gdrive_parser import GDriveParser
        record = GDriveParser.parse_to_record(file_path)
        return [record] if record else []
    elif source == "evernote" and file_path.suffix == ".html":
        from evernote_parser import EvernoteParser
        record = EvernoteParser.parse_to_record(file_path)
        return [record] if record else []
    elif source == "obsidian" and file_path.suffix == ".md":
        from obsidian_parser import ObsidianParser
        record = ObsidianParser.parse_to_record(file_path)
        return [record] if record else []
    return []


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------

def _process_record(note: NoteRecord, db, is_modify: bool = False) -> None:
    """Run a single NoteRecord through the full pipeline: dedup → classify → propose → route."""
    existing = db.get_note_by_path(note.source_path)
    if existing:
        if existing.id == note.id:
            return  # content unchanged; skip (prevents ghost events on multi-record files like Kindle)
        if not is_modify and existing.status not in (NoteStatus.PENDING, None):
            return  # already processed; skip re-ingestion (e.g. Kindle re-scan)
        note.id = existing.id
        note.version = existing.version + 1
        note.status = NoteStatus.PENDING

    if not note.body.strip():
        print(f"[SKIP]   {Path(note.source_path).name} — empty body, skipped")
        return

    db.upsert_note(note)
    print(f"[PARSE]  {Path(note.source_path).name} lang={note.language} words={note.word_count}")

    # Dedup check
    from dedup import check_duplicate
    dup_slug = check_duplicate(note.body)
    if dup_slug:
        print(f"[DEDUP]  Potential duplicate of [[{dup_slug}]] — merge proposal queued")
        db.set_note_status(note.id, NoteStatus.DUPLICATE_CANDIDATE)

    # Classify
    try:
        from classifier import classify
        primary, secondary = classify(note.body)
    except Exception as e:
        print(f"[ERROR] classify {note.id}: {e}")
        db.log_error(note.id, "classifying", str(e))
        return

    db.set_note_domain(note.id, primary, secondary)
    note.domain = primary
    note.secondary_domain = secondary
    print(f"[CLASSIFY] domain={primary}" + (f" (secondary: {secondary})" if secondary else ""))

    # Propose
    try:
        if note.note_type == "article":
            import uuid as _uuid
            from datetime import datetime as _dt, timezone as _tz
            from ollama_agent import generate_knowledge_card, _slugify
            from wiki_store import render_knowledge_card, find_related_article_pages
            from models import Proposal as _Proposal
            card_body = generate_knowledge_card(note)
            _slug = _slugify(note.title) or "article-note"
            related = find_related_article_pages(note.body, exclude_slug=_slug)
            card_body = render_knowledge_card(card_body, related_slugs=related)
            cfg = _load_settings()
            proposal = _Proposal(
                id=str(_uuid.uuid4()),
                note_id=note.id,
                note_version=note.version,
                proposed_page=_slug,
                is_new_page=True,
                link_only=False,
                summary=card_body,
                proposed_links=[],
                confidence=0.75,
                flag_contradiction=False,
                flag_duplicate=False,
                fast_track_eligible=False,
                ollama_model=cfg["ollama"]["model"],
                created_at=_dt.now(_tz.utc).isoformat(),
            )
        else:
            from ollama_agent import generate_proposal
            proposal = generate_proposal(note, primary)
    except ValueError as e:
        print(f"[ERROR] propose {note.id}: {e}")
        db.log_error(note.id, "proposing", str(e))
        db.set_note_status(note.id, NoteStatus.COMMIT_FAILED)
        return
    except Exception as e:
        print(f"[ERROR] propose {note.id}: {e}")
        db.log_error(note.id, "proposing", str(e))
        return

    db.save_proposal(proposal)

    # Route: fast-track or pending queue
    if proposal.fast_track_eligible:
        print(f"[FAST-TRACK] {proposal.proposed_page} conf={proposal.confidence:.2f}")
        db.set_proposal_decision(proposal.id, "fast_tracked")
        db.set_note_status(note.id, NoteStatus.FAST_TRACKED)
        _commit_fast_track(proposal, note)
    else:
        flag = "NEW" if proposal.is_new_page else "UPDATE"
        print(f"[GATE] {proposal.proposed_page} [{flag}] conf={proposal.confidence:.2f} → human review")
        db.set_note_status(note.id, NoteStatus.CLASSIFIED)


def _process_job(job: IngestJob) -> None:
    from db import get_db
    db = get_db()

    file_path = Path(job.path)

    if job.event == "delete":
        db.mark_deleted(str(file_path))
        print(f"[DELETE] {file_path.name} → status=deleted")
        return

    try:
        notes = _parse_note(file_path)
    except Exception as e:
        print(f"[ERROR] parse {file_path.name}: {e}")
        return

    for note in notes:
        _process_record(note, db, is_modify=(job.event == "modify"))


def _commit_fast_track(proposal, note: NoteRecord) -> None:
    """Commit a fast-tracked proposal and append to batch_log.jsonl."""
    from commit import commit as do_commit
    from db import get_db
    cfg = _load_settings()

    try:
        do_commit(proposal, note)
        log_entry = {
            "proposal_id": proposal.id,
            "slug": proposal.proposed_page,
            "note_id": note.id,
            "confidence": proposal.confidence,
            "model": proposal.ollama_model,
            "committed_at": datetime.now(timezone.utc).isoformat(),
        }
        batch_log = Path(__file__).parent.parent / cfg["paths"]["batch_log"]
        with open(batch_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")
        print(f"[COMMITTED] {proposal.proposed_page} → batch_log.jsonl")
    except Exception as e:
        print(f"[ERROR] fast-track commit failed: {e}")
        db = get_db()
        db.log_error(note.id, "committing", str(e))


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def process_single(path: str) -> None:
    """Process a single file without starting the daemon."""
    job = IngestJob(path=path, event="create")
    _process_job(job)


def replay_commits() -> None:
    """Replay all commits stuck in status='committing'."""
    from commit import replay_unfinished_commits
    replay_unfinished_commits()
    print("[REPLAY] Done")


def run_daemon() -> None:
    """Start the file watcher daemon."""
    cfg = _load_settings()
    raw_dir = Path(__file__).parent.parent / cfg["paths"]["raw_data"]
    debounce = cfg["ingestion"]["debounce_seconds"]

    # Replay any unfinished commits from a previous run
    replay_commits()

    handler = RawSourceHandler(debounce=debounce)
    observer = Observer()
    observer.schedule(handler, str(raw_dir), recursive=True)
    observer.start()
    print(f"[WATCHER] Monitoring {raw_dir} (debounce={debounce}s)")

    try:
        while True:
            try:
                job = _ingest_queue.get(timeout=1.0)
                _process_job(job)
            except queue.Empty:
                pass
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        print("[WATCHER] Stopped")


if __name__ == "__main__":
    if "--replay" in sys.argv:
        replay_commits()
    elif "--once" in sys.argv:
        idx = sys.argv.index("--once")
        if idx + 1 < len(sys.argv):
            process_single(sys.argv[idx + 1])
        else:
            print("Usage: python src/watcher.py --once PATH")
    else:
        run_daemon()
