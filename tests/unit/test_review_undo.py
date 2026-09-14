"""
Unit tests for db.undo_rejection() and db.get_rejected_notes().
"""
import sys
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from db import DB
from models import NoteStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_ago(n: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


@pytest.fixture()
def db(tmp_path) -> DB:
    d = DB(str(tmp_path / "test.sqlite"))
    d.init_schema()
    return d


def _insert_note(db: DB, note_id: str, status: str = "rejected") -> None:
    with db._conn() as conn:
        conn.execute(
            """INSERT INTO notes
               (id, source_path, title, language, source, domain, status,
                word_count, version, created_at, modified_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (note_id, f"/tmp/{note_id}.md", f"Note {note_id}", "en",
             "evernote", "philosophy", status, 100, 1, _now(), _now()),
        )


def _insert_proposal(db: DB, proposal_id: str, note_id: str, decision: str = "rejected") -> None:
    with db._conn() as conn:
        conn.execute(
            """INSERT INTO proposals
               (id, note_id, note_version, proposed_page, is_new_page, link_only,
                summary, proposed_links, confidence, flag_contradiction, flag_duplicate,
                fast_track_eligible, ollama_model, created_at, decision, rejection_reason,
                decided_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (proposal_id, note_id, 1, "some-wiki-page", 0, 0,
             "A summary.", "[]", 0.7, 0, 0, 0, "qwen3.5:9b", _now(),
             decision, "accidental" if decision == "rejected" else None,
             _now() if decision else None),
        )


def test_undo_rejection_clears_proposal_decision(db):
    _insert_note(db, "note1", status="rejected")
    _insert_proposal(db, "prop1", "note1", decision="rejected")

    db.undo_rejection("prop1", "note1")

    with db._conn() as conn:
        row = conn.execute("SELECT decision, rejection_reason, decided_at FROM proposals WHERE id='prop1'").fetchone()
    assert row["decision"] is None
    assert row["rejection_reason"] is None
    assert row["decided_at"] is None


def test_undo_rejection_restores_note_to_classified(db):
    _insert_note(db, "note1", status="rejected")
    _insert_proposal(db, "prop1", "note1", decision="rejected")

    db.undo_rejection("prop1", "note1")

    with db._conn() as conn:
        row = conn.execute("SELECT status FROM notes WHERE id='note1'").fetchone()
    assert row["status"] == NoteStatus.CLASSIFIED


def test_get_rejected_notes_returns_recent_rejections(db):
    _insert_note(db, "note1", status="rejected")
    _insert_proposal(db, "prop1", "note1", decision="rejected")

    results = db.get_rejected_notes(days=30)

    assert len(results) == 1
    note, proposal_id, proposed_page, decided_at = results[0]
    assert note.id == "note1"
    assert proposal_id == "prop1"
    assert proposed_page == "some-wiki-page"


def test_get_rejected_notes_excludes_old_rejections(db):
    _insert_note(db, "note-old", status="rejected")
    _insert_proposal(db, "prop-old", "note-old", decision="rejected")

    # Manually backdate the modified_at to 40 days ago
    with db._conn() as conn:
        conn.execute(
            "UPDATE notes SET modified_at=? WHERE id='note-old'",
            (_days_ago(40),),
        )

    results = db.get_rejected_notes(days=30)
    assert len(results) == 0


def test_get_rejected_notes_excludes_non_rejected(db):
    _insert_note(db, "note-classified", status="classified")
    _insert_proposal(db, "prop-c", "note-classified", decision=None)

    results = db.get_rejected_notes(days=30)
    assert len(results) == 0


def test_undo_rejection_makes_proposal_appear_in_pending(db):
    _insert_note(db, "note1", status="rejected")
    _insert_proposal(db, "prop1", "note1", decision="rejected")

    db.undo_rejection("prop1", "note1")

    pending = db.get_pending_proposals()
    assert any(p.id == "prop1" for p in pending)
