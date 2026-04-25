"""
SQLite wrapper for Second Brain v2 — metadata store and commit coordinator.
All state machine transitions go through this module.
"""
import json
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, List, Optional

from models import CommitRecord, ErrorRecord, NoteRecord, NoteStatus, Proposal


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS notes (
    id              TEXT PRIMARY KEY,
    source_path     TEXT UNIQUE NOT NULL,
    title           TEXT NOT NULL,
    language        TEXT NOT NULL,
    source          TEXT NOT NULL,
    domain          TEXT,
    secondary_domain TEXT,
    note_type       TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    wiki_page       TEXT,
    word_count      INTEGER NOT NULL DEFAULT 0,
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL,
    modified_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    id                  TEXT PRIMARY KEY,
    note_id             TEXT NOT NULL REFERENCES notes(id),
    note_version        INTEGER NOT NULL,
    proposed_page       TEXT NOT NULL,
    is_new_page         INTEGER NOT NULL,
    link_only           INTEGER NOT NULL,
    summary             TEXT NOT NULL,
    proposed_links      TEXT NOT NULL,
    confidence          REAL NOT NULL,
    flag_contradiction  INTEGER NOT NULL,
    flag_duplicate      INTEGER NOT NULL,
    fast_track_eligible INTEGER NOT NULL,
    ollama_model        TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    decision            TEXT,
    rejection_reason    TEXT,
    decided_at          TEXT,
    edited_content      TEXT
);

CREATE TABLE IF NOT EXISTS commits (
    id              TEXT PRIMARY KEY,
    proposal_id     TEXT NOT NULL REFERENCES proposals(id),
    status          TEXT NOT NULL,
    git_hash        TEXT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS errors (
    id              TEXT PRIMARY KEY,
    note_id         TEXT NOT NULL REFERENCES notes(id),
    stage           TEXT NOT NULL,
    error_message   TEXT NOT NULL,
    occurred_at     TEXT NOT NULL,
    resolved        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_notes_status      ON notes(status);
CREATE INDEX IF NOT EXISTS idx_notes_domain      ON notes(domain);
CREATE INDEX IF NOT EXISTS idx_proposals_note_id ON proposals(note_id);
CREATE INDEX IF NOT EXISTS idx_commits_status    ON commits(status);
CREATE INDEX IF NOT EXISTS idx_errors_resolved   ON errors(resolved);
"""


class DB:
    def __init__(self, db_path: str):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.executescript("PRAGMA journal_mode=WAL;")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA_SQL)
            # Migration: add note_type column to existing DBs (idempotent)
            try:
                conn.execute("ALTER TABLE notes ADD COLUMN note_type TEXT")
            except Exception:
                pass  # column already exists
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_note_type ON notes(note_type)")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Note CRUD
    # ------------------------------------------------------------------

    def upsert_note(self, note: NoteRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO notes
                    (id, source_path, title, language, source, domain, secondary_domain,
                     note_type, status, wiki_page, word_count, version, created_at, modified_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    modified_at=excluded.modified_at,
                    version=version+1,
                    status=excluded.status
                """,
                (
                    note.id, note.source_path, note.title, note.language,
                    note.source, note.domain, note.secondary_domain,
                    note.note_type, note.status, note.wiki_page, note.word_count,
                    note.version, note.created_at, note.modified_at,
                ),
            )

    def get_note(self, note_id: str) -> Optional[NoteRecord]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if not row:
            return None
        return self._row_to_note(row)

    def has_notes_with_path_prefix(self, prefix: str) -> bool:
        """Return True if any note has source_path starting with prefix.
        Used to detect multi-record files (e.g. Kindle) that have been ingested."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM notes WHERE source_path LIKE ? LIMIT 1",
                (f"{prefix}%",),
            ).fetchone()
        return row is not None

    def get_note_by_path(self, source_path: str) -> Optional[NoteRecord]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE source_path=?", (source_path,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_note(row)

    def set_note_status(
        self,
        note_id: str,
        status: str,
        wiki_page: Optional[str] = None,
    ) -> None:
        with self._conn() as conn:
            if wiki_page is not None:
                conn.execute(
                    "UPDATE notes SET status=?, wiki_page=?, modified_at=? WHERE id=?",
                    (status, wiki_page, _now(), note_id),
                )
            else:
                conn.execute(
                    "UPDATE notes SET status=?, modified_at=? WHERE id=?",
                    (status, _now(), note_id),
                )

    def get_notes_by_path_prefix(self, prefix: str) -> List[NoteRecord]:
        """Return all notes whose source_path starts with prefix."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM notes WHERE source_path LIKE ?",
                (f"{prefix}%",),
            ).fetchall()
        return [self._row_to_note(r) for r in rows]

    def delete_note(self, note_id: str) -> None:
        """Delete a note record by ID. Orphaned proposals are acceptable."""
        with self._conn() as conn:
            conn.execute("DELETE FROM notes WHERE id=?", (note_id,))

    def mark_deleted(self, source_path: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE notes SET status=?, modified_at=? WHERE source_path=?",
                (NoteStatus.DELETED, _now(), source_path),
            )

    def get_notes_by_wiki_page(self, wiki_page: str) -> list[str]:
        """Return note IDs whose wiki_page matches the given slug."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id FROM notes WHERE wiki_page=?", (wiki_page,)
            ).fetchall()
        return [row["id"] for row in rows]

    def clear_wiki_page(self, wiki_page: str) -> None:
        """Set wiki_page=NULL for all notes referencing the given slug."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE notes SET wiki_page=NULL, modified_at=? WHERE wiki_page=?",
                (_now(), wiki_page),
            )

    def set_note_domain(
        self,
        note_id: str,
        domain: str,
        secondary_domain: Optional[str] = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE notes SET domain=?, secondary_domain=?, status=?, modified_at=? WHERE id=?",
                (domain, secondary_domain, NoteStatus.CLASSIFIED, _now(), note_id),
            )

    # ------------------------------------------------------------------
    # Proposal CRUD
    # ------------------------------------------------------------------

    def save_proposal(self, proposal: Proposal) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO proposals
                    (id, note_id, note_version, proposed_page, is_new_page, link_only,
                     summary, proposed_links, confidence, flag_contradiction, flag_duplicate,
                     fast_track_eligible, ollama_model, created_at,
                     decision, rejection_reason, decided_at, edited_content)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    proposal.id, proposal.note_id, proposal.note_version,
                    proposal.proposed_page, int(proposal.is_new_page),
                    int(proposal.link_only), proposal.summary,
                    json.dumps(proposal.proposed_links), proposal.confidence,
                    int(proposal.flag_contradiction), int(proposal.flag_duplicate),
                    int(proposal.fast_track_eligible), proposal.ollama_model,
                    proposal.created_at, proposal.decision,
                    proposal.rejection_reason, proposal.decided_at,
                    proposal.edited_content,
                ),
            )

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM proposals WHERE id=?", (proposal_id,)
            ).fetchone()
        if not row:
            return None
        return self._row_to_proposal(row)

    def get_pending_proposals(
        self,
        domain: Optional[str] = None,
        note_type: Optional[str] = None,
    ) -> List[Proposal]:
        clauses = ["p.decision IS NULL", "p.fast_track_eligible=0"]
        params: list = []
        if domain:
            clauses.append("n.domain=?")
            params.append(domain)
        if note_type:
            clauses.append("n.note_type=?")
            params.append(note_type)
        where = " AND ".join(clauses)
        with self._conn() as conn:
            rows = conn.execute(
                f"""SELECT p.* FROM proposals p
                    JOIN notes n ON p.note_id = n.id
                    WHERE {where}
                    ORDER BY p.created_at ASC""",
                params,
            ).fetchall()
        return [self._row_to_proposal(r) for r in rows]

    def set_proposal_decision(
        self,
        proposal_id: str,
        decision: str,
        rejection_reason: Optional[str] = None,
        edited_content: Optional[str] = None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """UPDATE proposals SET decision=?, rejection_reason=?,
                   decided_at=?, edited_content=? WHERE id=?""",
                (decision, rejection_reason, _now(), edited_content, proposal_id),
            )

    def undo_rejection(self, proposal_id: str, note_id: str) -> None:
        """Reverse a rejection: clear proposal decision and restore note to classified."""
        with self._conn() as conn:
            conn.execute(
                """UPDATE proposals SET decision=NULL, rejection_reason=NULL,
                   decided_at=NULL WHERE id=?""",
                (proposal_id,),
            )
            conn.execute(
                "UPDATE notes SET status=?, modified_at=? WHERE id=?",
                (NoteStatus.CLASSIFIED, _now(), note_id),
            )

    def get_rejected_notes(self, days: int = 30) -> List[tuple]:
        """Return (NoteRecord, proposal_id, proposed_page, decided_at) for recently rejected notes."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT n.*, p.id AS proposal_id, p.proposed_page, p.decided_at AS p_decided_at
                   FROM notes n
                   JOIN proposals p ON p.note_id = n.id
                   WHERE n.status='rejected'
                     AND n.modified_at >= datetime('now', '-' || ? || ' days')
                   ORDER BY n.modified_at DESC""",
                (days,),
            ).fetchall()
        return [
            (self._row_to_note(r), r["proposal_id"], r["proposed_page"], r["p_decided_at"])
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Commit coordination
    # ------------------------------------------------------------------

    def begin_commit(self, proposal_id: str) -> str:
        import uuid
        commit_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO commits (id, proposal_id, status, started_at) VALUES (?,?,?,?)",
                (commit_id, proposal_id, "committing", _now()),
            )
        return commit_id

    def finish_commit(self, commit_id: str, git_hash: Optional[str] = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE commits SET status='committed', git_hash=?, finished_at=? WHERE id=?",
                (git_hash, _now(), commit_id),
            )

    def fail_commit(self, commit_id: str, error_message: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE commits SET status='failed', error_message=?, finished_at=? WHERE id=?",
                (error_message, _now(), commit_id),
            )

    def get_commits_by_status(self, status: str) -> List[CommitRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM commits WHERE status=?", (status,)
            ).fetchall()
        return [self._row_to_commit(r) for r in rows]

    def get_commit_git_hash(self, proposal_id: str) -> Optional[str]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT git_hash FROM commits WHERE proposal_id=? AND status='committed'",
                (proposal_id,),
            ).fetchone()
        return row["git_hash"] if row else None

    # ------------------------------------------------------------------
    # Error log
    # ------------------------------------------------------------------

    def log_error(self, note_id: str, stage: str, error_message: str) -> None:
        import uuid
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO errors (id, note_id, stage, error_message, occurred_at) VALUES (?,?,?,?,?)",
                (str(uuid.uuid4()), note_id, stage, error_message, _now()),
            )

    def get_unresolved_errors(self) -> List[ErrorRecord]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM errors WHERE resolved=0 ORDER BY occurred_at DESC"
            ).fetchall()
        return [
            ErrorRecord(
                id=r["id"], note_id=r["note_id"], stage=r["stage"],
                error_message=r["error_message"], occurred_at=r["occurred_at"],
                resolved=r["resolved"],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _row_to_note(self, row: sqlite3.Row) -> NoteRecord:
        return NoteRecord(
            id=row["id"], title=row["title"], body="", tags=[],
            language=row["language"], source=row["source"],
            source_path=row["source_path"],
            created_at=row["created_at"], modified_at=row["modified_at"],
            version=row["version"], domain=row["domain"],
            secondary_domain=row["secondary_domain"],
            status=row["status"], wiki_page=row["wiki_page"],
            word_count=row["word_count"],
            note_type=row["note_type"] if "note_type" in row.keys() else None,
        )

    def _row_to_proposal(self, row: sqlite3.Row) -> Proposal:
        return Proposal(
            id=row["id"], note_id=row["note_id"], note_version=row["note_version"],
            proposed_page=row["proposed_page"],
            is_new_page=bool(row["is_new_page"]),
            link_only=bool(row["link_only"]),
            summary=row["summary"],
            proposed_links=json.loads(row["proposed_links"]),
            confidence=row["confidence"],
            flag_contradiction=bool(row["flag_contradiction"]),
            flag_duplicate=bool(row["flag_duplicate"]),
            fast_track_eligible=bool(row["fast_track_eligible"]),
            ollama_model=row["ollama_model"],
            created_at=row["created_at"],
            decision=row["decision"],
            rejection_reason=row["rejection_reason"],
            decided_at=row["decided_at"],
            edited_content=row["edited_content"],
        )

    def _row_to_commit(self, row: sqlite3.Row) -> CommitRecord:
        return CommitRecord(
            id=row["id"], proposal_id=row["proposal_id"],
            status=row["status"], started_at=row["started_at"],
            git_hash=row["git_hash"], finished_at=row["finished_at"],
            error_message=row["error_message"],
        )


def _load_settings() -> dict:
    import yaml
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def get_db() -> DB:
    cfg = _load_settings()
    return DB(cfg["paths"]["db"])


if __name__ == "__main__":
    if "--init" in sys.argv:
        db = get_db()
        db.init_schema()
        print(f"[OK] Schema initialized at {db.db_path}")
    else:
        print("Usage: python src/db.py --init")
