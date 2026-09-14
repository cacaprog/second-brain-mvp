"""
Unit tests for slug_migrator.py — DB.rename_wiki_page and the migration engine
(heuristic scan, idempotency, regeneration, collision resolution, apply, detect).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from db import DB
import slug_migrator
from slug_migrator import MigrationCandidate, cmd_apply, cmd_detect


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# DB.rename_wiki_page
# ---------------------------------------------------------------------------

@pytest.fixture()
def db(tmp_path) -> DB:
    d = DB(str(tmp_path / "test.sqlite"))
    d.init_schema()
    return d


def _insert_note(db: DB, note_id: str, wiki_page) -> None:
    with db._conn() as conn:
        conn.execute(
            """INSERT INTO notes
               (id, source_path, title, language, source, domain, wiki_page,
                status, word_count, version, created_at, modified_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (note_id, f"/tmp/{note_id}.md", f"Note {note_id}", "en", "kindle",
             "philosophy", wiki_page, "committed", 100, 1, _now(), _now()),
        )


def test_rename_wiki_page_repoints_matching_notes(db):
    _insert_note(db, "n1", "old-slug")
    _insert_note(db, "n2", "old-slug")
    _insert_note(db, "n3", "unrelated-slug")

    db.rename_wiki_page("old-slug", "new-slug")

    assert db.get_notes_by_wiki_page("new-slug") == ["n1", "n2"] or set(
        db.get_notes_by_wiki_page("new-slug")
    ) == {"n1", "n2"}
    assert db.get_notes_by_wiki_page("old-slug") == []
    assert db.get_notes_by_wiki_page("unrelated-slug") == ["n3"]


def _insert_proposal(db: DB, proposal_id: str, note_id: str, proposed_page: str) -> None:
    with db._conn() as conn:
        conn.execute(
            """INSERT INTO proposals
               (id, note_id, note_version, proposed_page, is_new_page, link_only,
                summary, proposed_links, confidence, flag_contradiction, flag_duplicate,
                fast_track_eligible, ollama_model, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (proposal_id, note_id, 1, proposed_page, 1, 0, "summary", "[]",
             0.75, 0, 0, 0, "qwen3.5:latest", _now()),
        )


def test_update_proposed_page_changes_only_target_proposal(db):
    _insert_note(db, "n1", None)
    _insert_note(db, "n2", None)
    _insert_proposal(db, "p1", "n1", "old-bad-slug")
    _insert_proposal(db, "p2", "n2", "other-slug")

    db.update_proposed_page("p1", "new-good-slug")

    assert db.get_proposal("p1").proposed_page == "new-good-slug"
    assert db.get_proposal("p2").proposed_page == "other-slug"


# ---------------------------------------------------------------------------
# Fake wiki fixture
# ---------------------------------------------------------------------------

PAGE_TEMPLATE = """---
slug: {slug}
domain: {domain}
note_type: rich_note
languages:
- en
created: '2026-01-01'
updated: '2026-01-01'
version: 1
sources: []
links: []
confidence: 0.8
---

## {title}

Some body text about {title}.
"""


def _write_page(wiki_root: Path, domain: str, slug: str, title: str = "Concept") -> Path:
    d = wiki_root / "domains" / domain
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{slug}.md"
    p.write_text(PAGE_TEMPLATE.format(slug=slug, domain=domain, title=title), encoding="utf-8")
    return p


@pytest.fixture()
def fake_wiki(tmp_path):
    wiki_root = tmp_path / "wiki"
    (wiki_root / "domains").mkdir(parents=True)
    with patch("wiki_store._wiki_root", return_value=wiki_root):
        yield wiki_root


# ---------------------------------------------------------------------------
# _flag_candidates — heuristic scan
# ---------------------------------------------------------------------------

def test_flag_candidates_flags_long_truncated_slug(fake_wiki):
    _write_page(fake_wiki, "health", "sprint-how-to-solve-big-problems-and-tes")
    candidates = slug_migrator._flag_candidates()
    flagged = {c.old_slug for c in candidates}
    assert "sprint-how-to-solve-big-problems-and-tes" in flagged


def test_flag_candidates_flags_too_many_words(fake_wiki):
    _write_page(fake_wiki, "marketing", "tribes-we-need-you-to-lead-us")
    candidates = slug_migrator._flag_candidates()
    flagged = {c.old_slug for c in candidates}
    assert "tribes-we-need-you-to-lead-us" in flagged


def test_flag_candidates_flags_hyphen_artifact(fake_wiki):
    _write_page(fake_wiki, "theology", "ciencia-e-fe---a-particula-de-deus")
    candidates = slug_migrator._flag_candidates()
    flagged = {c.old_slug for c in candidates}
    assert "ciencia-e-fe---a-particula-de-deus" in flagged


def test_flag_candidates_leaves_good_slug_untouched(fake_wiki):
    _write_page(fake_wiki, "philosophy", "antifragilidade")
    candidates = slug_migrator._flag_candidates()
    flagged = {c.old_slug for c in candidates}
    assert "antifragilidade" not in flagged


def test_flag_candidates_skips_queries_domain(fake_wiki):
    _write_page(fake_wiki, "queries", "a-very-long-query-derived-slug-that-would-otherwise-be-flagged")
    candidates = slug_migrator._flag_candidates()
    flagged = {c.old_slug for c in candidates}
    assert "a-very-long-query-derived-slug-that-would-otherwise-be-flagged" not in flagged


def test_flag_candidates_skips_already_migrated(fake_wiki):
    _write_page(fake_wiki, "health", "sprint-how-to-solve-big-problems-and-tes")
    with patch("slug_migrator._already_migrated_slugs", return_value={"sprint-how-to-solve-big-problems-and-tes"}):
        candidates = slug_migrator._flag_candidates()
    flagged = {c.old_slug for c in candidates}
    assert "sprint-how-to-solve-big-problems-and-tes" not in flagged


# ---------------------------------------------------------------------------
# _already_migrated_slugs — idempotency via wiki git history
# ---------------------------------------------------------------------------

def test_already_migrated_slugs_parses_rename_commits(fake_wiki):
    git_log_output = (
        "abc123 rename: old-slug-a → new-slug-a\n"
        "def456 ingest: unrelated-page (confidence=0.80, model=qwen3.5:9b)\n"
        "ghi789 rename: old-slug-b → new-slug-b\n"
    )
    fake_result = MagicMock(stdout=git_log_output, returncode=0)
    with patch("slug_migrator.subprocess.run", return_value=fake_result):
        migrated = slug_migrator._already_migrated_slugs()
    assert migrated == {"new-slug-a", "new-slug-b"}


# ---------------------------------------------------------------------------
# _regenerate_slug
# ---------------------------------------------------------------------------

def test_regenerate_slug_uses_ollama_and_cleans_result(fake_wiki):
    candidate = MigrationCandidate(domain="health", old_slug="x" * 40, new_slug=None, reasons=["length"])
    with patch("slug_migrator._call_ollama", return_value="Sprint Methodology"):
        new_slug = slug_migrator._regenerate_slug(candidate, "## Sprint\n\nBody about sprints.")
    assert new_slug == "sprint-methodology"


def test_regenerate_slug_strips_domain_suffix(fake_wiki):
    candidate = MigrationCandidate(domain="marketing", old_slug="x" * 40, new_slug=None, reasons=["length"])
    with patch("slug_migrator._call_ollama", return_value="tribes-leadership-marketing"):
        new_slug = slug_migrator._regenerate_slug(candidate, "## Tribes\n\nBody about tribes.")
    assert new_slug == "tribes-leadership"


# ---------------------------------------------------------------------------
# _build_candidates — regeneration landing back on the same slug
# ---------------------------------------------------------------------------

def test_build_candidates_marks_unchanged_when_regeneration_matches_old_slug(fake_wiki):
    old_slug = "generosity-vulnerability-accountability-candor"  # already 4 words, len<40
    _write_page(fake_wiki, "leadership", old_slug)
    with patch("slug_migrator._call_ollama", return_value="Generosity Vulnerability Accountability Candor"):
        candidates = slug_migrator._build_candidates()
    assert len(candidates) == 1
    c = candidates[0]
    assert c.status == "unchanged"
    assert c.new_slug == old_slug


def test_apply_skips_unchanged_candidates(fake_wiki):
    old_slug = "generosity-vulnerability-accountability-candor"
    _write_page(fake_wiki, "leadership", old_slug)
    with patch("slug_migrator._call_ollama", return_value="Generosity Vulnerability Accountability Candor"), \
         patch("slug_migrator.wiki_store.rename_wiki_page") as mock_rename, \
         patch("slug_migrator.get_db") as mock_get_db, \
         patch("slug_migrator.get_vector_store") as mock_get_vs:
        candidates = slug_migrator._build_candidates()
        for c in candidates:
            slug_migrator._apply_candidate(c, dry_run=False)

    mock_rename.assert_not_called()
    mock_get_db.assert_not_called()
    mock_get_vs.assert_not_called()


# ---------------------------------------------------------------------------
# _resolve_collisions
# ---------------------------------------------------------------------------

def test_resolve_collisions_disambiguates_same_domain_pair(fake_wiki):
    a = MigrationCandidate(domain="marketing", old_slug="old-a", new_slug="tribes", reasons=[], title="Tribes Leadership")
    b = MigrationCandidate(domain="marketing", old_slug="old-b", new_slug="tribes", reasons=[], title="Tribes Loyalty")
    slug_migrator._resolve_collisions([a, b])
    assert a.new_slug != b.new_slug
    assert a.status != "collision"
    assert b.status != "collision"


def test_resolve_collisions_marks_unresolvable_as_collision(fake_wiki):
    a = MigrationCandidate(domain="marketing", old_slug="old-a", new_slug="tribes", reasons=[], title="Tribes")
    b = MigrationCandidate(domain="marketing", old_slug="old-b", new_slug="tribes", reasons=[], title="Tribes")
    slug_migrator._resolve_collisions([a, b])
    assert a.status == "collision" or b.status == "collision"


def test_resolve_collisions_ignores_different_domains(fake_wiki):
    a = MigrationCandidate(domain="marketing", old_slug="old-a", new_slug="tribes", reasons=[], title="Tribes")
    b = MigrationCandidate(domain="leadership", old_slug="old-b", new_slug="tribes", reasons=[], title="Tribes")
    slug_migrator._resolve_collisions([a, b])
    assert a.new_slug == "tribes"
    assert b.new_slug == "tribes"
    assert a.status != "collision"


def test_resolve_collisions_disambiguates_against_existing_page(fake_wiki):
    _write_page(fake_wiki, "leadership", "tribes", title="Existing Unrelated Page")
    a = MigrationCandidate(domain="leadership", old_slug="old-a", new_slug="tribes", reasons=[], title="Tribes Leadership")
    slug_migrator._resolve_collisions([a])
    assert a.new_slug != "tribes"
    assert a.status != "collision"


def test_resolve_collisions_marks_collision_against_unresolvable_existing_page(fake_wiki):
    _write_page(fake_wiki, "leadership", "tribes", title="Existing Unrelated Page")
    a = MigrationCandidate(domain="leadership", old_slug="old-a", new_slug="tribes", reasons=[], title="Tribes")
    slug_migrator._resolve_collisions([a])
    assert a.status == "collision"


def test_resolve_collisions_own_old_slug_not_treated_as_existing(fake_wiki):
    # A candidate whose regenerated slug happens to equal its OWN current slug
    # must not be treated as colliding with "itself" on disk.
    _write_page(fake_wiki, "leadership", "tribes", title="Tribes")
    a = MigrationCandidate(domain="leadership", old_slug="tribes", new_slug="tribes", reasons=[], title="Tribes")
    slug_migrator._resolve_collisions([a])
    assert a.new_slug == "tribes"
    assert a.status != "collision"


# ---------------------------------------------------------------------------
# _apply_candidate — ordering and error containment
# ---------------------------------------------------------------------------

def test_apply_candidate_calls_wiki_db_vector_in_order(fake_wiki):
    _write_page(fake_wiki, "health", "old-slug")
    candidate = MigrationCandidate(domain="health", old_slug="old-slug", new_slug="new-slug", reasons=["length"])

    call_order = []
    mock_db = MagicMock()
    mock_db.get_notes_by_wiki_page.return_value = []
    mock_vs = MagicMock()

    def _record(name):
        def _inner(*a, **k):
            call_order.append(name)
        return _inner

    with patch("slug_migrator.wiki_store") as mock_ws, \
         patch("slug_migrator.get_db", return_value=mock_db), \
         patch("slug_migrator.get_vector_store", return_value=mock_vs):
        mock_ws.rename_wiki_page.side_effect = _record("wiki")
        mock_ws.read_wiki_page.return_value = "## Concept\n\nBody."
        mock_db.rename_wiki_page.side_effect = _record("db")
        mock_vs.delete_embedding.side_effect = _record("vector_delete")
        mock_vs.upsert.side_effect = _record("vector_upsert")

        slug_migrator._apply_candidate(candidate, dry_run=False)

    assert call_order == ["wiki", "db", "vector_delete", "vector_upsert"]
    assert candidate.status == "renamed"


def test_apply_candidate_dry_run_makes_no_calls(fake_wiki):
    candidate = MigrationCandidate(domain="health", old_slug="old-slug", new_slug="new-slug", reasons=["length"])
    with patch("slug_migrator.wiki_store") as mock_ws, \
         patch("slug_migrator.get_db") as mock_get_db, \
         patch("slug_migrator.get_vector_store") as mock_get_vs:
        slug_migrator._apply_candidate(candidate, dry_run=True)

    mock_ws.rename_wiki_page.assert_not_called()
    mock_get_db.assert_not_called()
    mock_get_vs.assert_not_called()


def test_apply_candidate_records_error_without_raising(fake_wiki):
    candidate = MigrationCandidate(domain="health", old_slug="old-slug", new_slug="new-slug", reasons=["length"])
    with patch("slug_migrator.wiki_store") as mock_ws:
        mock_ws.rename_wiki_page.side_effect = RuntimeError("boom")
        mock_ws.read_wiki_page.return_value = "## Concept\n\nBody."
        with patch("slug_migrator.get_db") as mock_get_db:
            mock_get_db.return_value.get_notes_by_wiki_page.return_value = []
            slug_migrator._apply_candidate(candidate, dry_run=False)

    assert candidate.status == "error"
    assert "boom" in candidate.error


# ---------------------------------------------------------------------------
# cmd_detect — read-only, zero writes
# ---------------------------------------------------------------------------

def test_cmd_detect_makes_no_writes(fake_wiki, capsys):
    _write_page(fake_wiki, "health", "sprint-how-to-solve-big-problems-and-tes")

    mock_db = MagicMock()
    mock_vs = MagicMock()
    with patch("slug_migrator._call_ollama", return_value="Sprint Methodology"), \
         patch("slug_migrator._already_migrated_slugs", return_value=set()), \
         patch("slug_migrator.get_db", return_value=mock_db), \
         patch("slug_migrator.get_vector_store", return_value=mock_vs), \
         patch("slug_migrator.wiki_store.rename_wiki_page") as mock_rename:
        args = argparse_namespace(path=None)
        cmd_detect(args)

    mock_rename.assert_not_called()
    mock_db.rename_wiki_page.assert_not_called()
    mock_vs.delete_embedding.assert_not_called()
    mock_vs.upsert.assert_not_called()

    out = capsys.readouterr().out
    assert "sprint-how-to-solve-big-problems-and-tes" in out
    assert "sprint-methodology" in out


def argparse_namespace(**kwargs):
    class _NS:
        pass
    ns = _NS()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns
