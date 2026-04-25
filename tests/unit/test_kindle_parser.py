"""
Unit tests for KindleParser multi-domain grouping logic.
Uses synthetic clippings strings — no real Kindle files needed.
"""
import sys
import textwrap
from pathlib import Path

import pytest

# Add src/ to path so imports work without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kindle_parser import KindleParser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SEP = "=========="


def _clipping(book: str, author: str, highlight: str) -> str:
    return f"{book} ({author})\n- Your Highlight at location 1 | Added: Friday, 1 January 2021\n\n{highlight}"


def _make_clippings(*entries: str) -> str:
    """Join entries with Kindle separator, add leading BOM-stripped header."""
    return f"\n{SEP}\n".join(entries) + f"\n{SEP}\n"


def _write_clippings(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "My Clippings.txt"
    f.write_text(content, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Domain seed constants (must match config/domains.yaml)
# ---------------------------------------------------------------------------

# philosophy seeds
P_SEEDS = ["Taleb", "stoicism", "estoicismo", "Hadot"]
# analytics seeds
A_SEEDS = ["attribution", "churn", "funil", "KPI", "dashboard"]


def _phi(n: int = 1) -> list[str]:
    """n highlight strings clearly in philosophy domain."""
    return [f"This text is about {P_SEEDS[i % len(P_SEEDS)]} philosophy concept number {i}" for i in range(n)]


def _ana(n: int = 1) -> list[str]:
    """n highlight strings clearly in analytics domain."""
    return [f"This text is about {A_SEEDS[i % len(A_SEEDS)]} analytics concept number {i}" for i in range(n)]


# ---------------------------------------------------------------------------
# T006 — test_all_highlights_captured
# ---------------------------------------------------------------------------

def test_all_highlights_captured(tmp_path):
    """Every highlight in a 20-highlight book must appear in NoteRecord bodies."""
    highlights = _phi(20)
    entries = [_clipping("Big Book", "Author One", h) for h in highlights]
    clippings_file = _write_clippings(tmp_path, _make_clippings(*entries))

    records = KindleParser.parse_to_records(clippings_file)

    # Reconstruct all individual highlights from returned records
    all_body_text = "\n\n---\n\n".join(r.body for r in records)
    # Each highlight appears in exactly one record
    for h in highlights:
        assert h in all_body_text, f"Highlight missing from output: {h!r}"


# ---------------------------------------------------------------------------
# T007 — test_multi_domain_book
# ---------------------------------------------------------------------------

def test_multi_domain_book(tmp_path):
    """A book with 10 philosophy + 10 analytics highlights → 2 NoteRecords."""
    phi_highlights = _phi(10)
    ana_highlights = _ana(10)
    all_highlights = phi_highlights + ana_highlights

    entries = [_clipping("Mixed Book", "Author Mixed", h) for h in all_highlights]
    clippings_file = _write_clippings(tmp_path, _make_clippings(*entries))

    records = KindleParser.parse_to_records(clippings_file)
    book_records = [r for r in records if "Mixed Book" in r.title]

    assert len(book_records) == 2, (
        f"Expected 2 domain records for mixed book, got {len(book_records)}: "
        f"{[r.title for r in book_records]}"
    )

    domains = {r.domain for r in book_records}
    assert "philosophy" in domains, f"philosophy domain missing, got: {domains}"
    assert "analytics" in domains, f"analytics domain missing, got: {domains}"

    # source_path must contain exactly 2 '#' (file#slug#domain format)
    for r in book_records:
        assert r.source_path.count("#") == 2, (
            f"source_path should have 2 '#', got: {r.source_path!r}"
        )

    # Titles must include domain suffix when multiple groups
    for r in book_records:
        assert "[" in r.title and "]" in r.title, (
            f"Multi-domain title should include domain suffix, got: {r.title!r}"
        )


# ---------------------------------------------------------------------------
# T008 — test_single_domain_book_no_split
# ---------------------------------------------------------------------------

def test_single_domain_book_no_split(tmp_path):
    """A book with 15 clearly philosophy highlights → exactly 1 NoteRecord."""
    highlights = _phi(15)
    entries = [_clipping("Pure Philosophy", "Author P", h) for h in highlights]
    clippings_file = _write_clippings(tmp_path, _make_clippings(*entries))

    records = KindleParser.parse_to_records(clippings_file)
    book_records = [r for r in records if "Pure Philosophy" in r.title]

    assert len(book_records) == 1, (
        f"Single-domain book must produce exactly 1 record, got {len(book_records)}"
    )

    # Title must NOT have domain suffix
    assert "[" not in book_records[0].title, (
        f"Single-domain title must not have suffix, got: {book_records[0].title!r}"
    )
    assert book_records[0].title == "Pure Philosophy"


# ---------------------------------------------------------------------------
# T010 — test_thin_group_merging
# ---------------------------------------------------------------------------

def test_thin_group_merging(tmp_path):
    """
    15 philosophy + 2 analytics highlights → thin analytics group (< 3)
    is merged into philosophy → 1 NoteRecord with all 17 highlights.
    """
    phi_highlights = _phi(15)
    ana_highlights = _ana(2)  # below min_group_size=3
    all_highlights = phi_highlights + ana_highlights

    entries = [_clipping("Mostly Philosophy", "Author MP", h) for h in all_highlights]
    clippings_file = _write_clippings(tmp_path, _make_clippings(*entries))

    records = KindleParser.parse_to_records(clippings_file)
    book_records = [r for r in records if "Mostly Philosophy" in r.title]

    assert len(book_records) == 1, (
        f"Thin group should be merged → 1 record, got {len(book_records)}: "
        f"{[(r.title, r.domain) for r in book_records]}"
    )

    # All 17 highlights must be present
    body = book_records[0].body
    for h in all_highlights:
        assert h in body, f"Highlight missing after thin-group merge: {h!r}"


# ---------------------------------------------------------------------------
# T011 — test_single_highlight_book
# ---------------------------------------------------------------------------

def test_single_highlight_book(tmp_path):
    """A book with exactly 1 highlight → 1 NoteRecord, no crash."""
    highlight = "Antifragility is about gaining from disorder."
    entries = [_clipping("Antifragile", "Nassim Taleb", highlight)]
    clippings_file = _write_clippings(tmp_path, _make_clippings(*entries))

    records = KindleParser.parse_to_records(clippings_file)
    book_records = [r for r in records if "Antifragile" in r.title]

    assert len(book_records) == 1, (
        f"Single-highlight book must produce 1 record, got {len(book_records)}"
    )
    assert highlight in book_records[0].body
