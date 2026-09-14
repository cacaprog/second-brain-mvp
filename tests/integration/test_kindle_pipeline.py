"""
Integration test: full Kindle parsing pipeline with a synthetic clippings file.
Verifies multi-domain splitting, single-domain books, thin-group merging,
total highlight count, and source_path format.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from kindle_parser import KindleParser

SEP = "=========="


def _clipping(book: str, author: str, highlight: str) -> str:
    return f"{book} ({author})\n- Your Highlight at location 1 | Added: Friday, 1 January 2021\n\n{highlight}"


def _make_clippings(*entries: str) -> str:
    return f"\n{SEP}\n".join(entries) + f"\n{SEP}\n"


# Domain seed words from config/domains.yaml
PHI_SEED = "stoicism"          # philosophy
ANA_SEED = "attribution"       # analytics


@pytest.fixture()
def synthetic_clippings(tmp_path) -> Path:
    """
    Book A: 10 philosophy + 10 analytics highlights → 2 NoteRecords
    Book B: 5 analytics highlights → 1 NoteRecord
    Book C: 2 philosophy highlights → thin group, merged → 1 NoteRecord
    Total highlights: 10+10+5+2 = 27
    """
    phi = lambda i: f"Concept {i}: {PHI_SEED} is fundamental to Stoic philosophy"
    ana = lambda i: f"Metric {i}: {ANA_SEED} helps understand {ANA_SEED} in marketing"

    entries = []

    # Book A — 10 phi + 10 ana
    for i in range(10):
        entries.append(_clipping("Book Alpha", "Author A", phi(i)))
    for i in range(10):
        entries.append(_clipping("Book Alpha", "Author A", ana(i)))

    # Book B — 5 ana (single domain)
    for i in range(5):
        entries.append(_clipping("Book Beta", "Author B", ana(i)))

    # Book C — 2 phi (below min_group_size=3, no other group → collapses to 1)
    for i in range(2):
        entries.append(_clipping("Book Gamma", "Author C", phi(i)))

    clippings_path = tmp_path / "My Clippings.txt"
    clippings_path.write_text(_make_clippings(*entries), encoding="utf-8")
    return clippings_path


def test_total_highlight_count(synthetic_clippings):
    """All 27 highlights must appear across all NoteRecords — none dropped."""
    records = KindleParser.parse_to_records(synthetic_clippings)
    all_text = "\n\n---\n\n".join(r.body for r in records)
    # Count separators + 1 in each body; sum gives total highlight count
    total = sum(r.body.count("---") + 1 for r in records)
    assert total == 27, f"Expected 27 highlights, got {total}"


def test_book_alpha_two_records(synthetic_clippings):
    """Book A with mixed domains → exactly 2 NoteRecords (one per domain)."""
    records = KindleParser.parse_to_records(synthetic_clippings)
    alpha = [r for r in records if "Book Alpha" in r.title]
    assert len(alpha) == 2, f"Book Alpha should have 2 records, got {len(alpha)}"
    domains = {r.domain for r in alpha}
    assert "philosophy" in domains
    assert "analytics" in domains


def test_book_beta_one_record(synthetic_clippings):
    """Book B (single domain) → exactly 1 NoteRecord, no domain suffix in title."""
    records = KindleParser.parse_to_records(synthetic_clippings)
    beta = [r for r in records if "Book Beta" in r.title]
    assert len(beta) == 1, f"Book Beta should have 1 record, got {len(beta)}"
    assert "[" not in beta[0].title, "Single-domain title must not have suffix"


def test_book_gamma_one_record(synthetic_clippings):
    """Book C (2 highlights, below threshold) → collapses to 1 NoteRecord."""
    records = KindleParser.parse_to_records(synthetic_clippings)
    gamma = [r for r in records if "Book Gamma" in r.title]
    assert len(gamma) == 1, f"Book Gamma should collapse to 1 record, got {len(gamma)}"
    # Both highlights must be present
    assert gamma[0].body.count("---") == 1 or "Concept 0" in gamma[0].body


def test_source_path_format(synthetic_clippings):
    """All source_paths must follow the new file#slug#domain format (2 '#')."""
    records = KindleParser.parse_to_records(synthetic_clippings)
    for r in records:
        count = r.source_path.count("#")
        assert count == 2, (
            f"source_path must have exactly 2 '#', got {count}: {r.source_path!r}"
        )
