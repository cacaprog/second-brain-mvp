"""Unit tests for pdf_parser.py"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from pdf_parser import parse


def _make_mock_doc(pages_text: list[str], title: str = ""):
    """Build a minimal fitz.open() mock returning the given per-page texts."""
    mock_doc = MagicMock()
    mock_pages = [MagicMock() for _ in pages_text]
    for page_mock, text in zip(mock_pages, pages_text):
        page_mock.get_text.return_value = text
    mock_doc.__iter__ = MagicMock(return_value=iter(mock_pages))
    mock_doc.metadata = {"title": title}
    mock_doc.close = MagicMock()
    return mock_doc


@pytest.fixture
def tmp_pdf(tmp_path):
    """Create a dummy PDF file (content doesn't matter — fitz is mocked)."""
    p = tmp_path / "test.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    return p


def test_pdf_with_text_produces_note_record(tmp_pdf):
    mock_doc = _make_mock_doc(["Introduction\n\nThis paper studies neural networks."])
    with patch("fitz.open", return_value=mock_doc):
        record = parse(tmp_pdf)
    assert record is not None
    assert "neural networks" in record.body.lower()


def test_image_only_pdf_returns_none(tmp_pdf):
    mock_doc = _make_mock_doc(["", "   ", ""])
    with patch("fitz.open", return_value=mock_doc):
        record = parse(tmp_pdf)
    assert record is None


def test_body_truncated_at_12000_chars(tmp_pdf):
    long_text = "word " * 5000  # > 12000 chars
    mock_doc = _make_mock_doc([long_text])
    with patch("fitz.open", return_value=mock_doc):
        record = parse(tmp_pdf)
    assert record is not None
    assert len(record.body) <= 12000


def test_note_type_is_always_article(tmp_pdf):
    mock_doc = _make_mock_doc(["Some research content here."])
    with patch("fitz.open", return_value=mock_doc):
        record = parse(tmp_pdf)
    assert record is not None
    assert record.note_type == "article"


def test_source_is_always_papers(tmp_pdf):
    mock_doc = _make_mock_doc(["Some research content here."])
    with patch("fitz.open", return_value=mock_doc):
        record = parse(tmp_pdf)
    assert record is not None
    assert record.source == "papers"


def test_title_from_pdf_metadata(tmp_pdf):
    mock_doc = _make_mock_doc(["Body text content."], title="Attention Is All You Need")
    with patch("fitz.open", return_value=mock_doc):
        record = parse(tmp_pdf)
    assert record is not None
    assert record.title == "Attention Is All You Need"


def test_title_falls_back_to_filename_when_metadata_empty(tmp_pdf):
    mock_doc = _make_mock_doc(["Body text content."], title="")
    with patch("fitz.open", return_value=mock_doc):
        record = parse(tmp_pdf)
    assert record is not None
    assert record.title == tmp_pdf.stem
