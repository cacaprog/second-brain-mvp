"""Unit tests for article_parser.py"""
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from article_parser import parse, extract_source_url


@pytest.fixture
def tmp_article(tmp_path):
    def _make(content: str, name: str = "test.md") -> Path:
        p = tmp_path / name
        p.write_text(content, encoding="utf-8")
        return p
    return _make


def test_full_front_matter_extracts_title_url_body(tmp_article):
    content = textwrap.dedent("""\
        ---
        title: "Attention Is All You Need"
        url: https://arxiv.org/abs/1706.03762
        tags: [machine-learning]
        ---

        The transformer architecture relies on self-attention mechanisms.
        It achieves state-of-the-art results on translation tasks.
    """)
    record = parse(tmp_article(content))
    assert record is not None
    assert record.title == "Attention Is All You Need"
    assert "url:https://arxiv.org/abs/1706.03762" in record.tags
    assert "transformer" in record.body.lower()


def test_no_front_matter_uses_h1_as_title(tmp_article):
    content = "# My Research Note\n\nThis is about machine learning and neural networks.\n"
    record = parse(tmp_article(content))
    assert record is not None
    assert record.title == "My Research Note"


def test_no_h1_uses_filename_as_title(tmp_article):
    content = "Just some body text without any header.\n"
    p = tmp_article(content, name="my-article.md")
    record = parse(p)
    assert record is not None
    assert record.title == "my-article"


def test_empty_file_returns_none(tmp_article):
    record = parse(tmp_article("   \n  \n"))
    assert record is None


def test_note_type_is_always_article(tmp_article):
    content = "# Test\n\nSome content about an interesting topic.\n"
    record = parse(tmp_article(content))
    assert record is not None
    assert record.note_type == "article"


def test_source_is_always_articles(tmp_article):
    content = "# Test\n\nSome content about an interesting topic.\n"
    record = parse(tmp_article(content))
    assert record is not None
    assert record.source == "articles"


def test_body_truncated_at_12000_chars(tmp_article):
    content = "# Big Article\n\n" + "x " * 10000
    record = parse(tmp_article(content))
    assert record is not None
    assert len(record.body) <= 12000


def test_extract_source_url_from_front_matter(tmp_article):
    content = textwrap.dedent("""\
        ---
        title: Test
        url: https://example.com/article
        ---
        Body text.
    """)
    p = tmp_article(content)
    url = extract_source_url(p)
    assert url == "https://example.com/article"


def test_extract_source_url_returns_none_when_absent(tmp_article):
    content = "# No URL\n\nBody text here.\n"
    p = tmp_article(content)
    assert extract_source_url(p) is None
