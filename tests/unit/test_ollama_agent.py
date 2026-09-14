"""
Unit tests for ollama_agent.py — generate_proposal() slug handling.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from models import NoteRecord
from ollama_agent import generate_proposal


def _make_note(title: str = "A Note About Something", domain: str = "philosophy") -> NoteRecord:
    return NoteRecord(
        id="deadbeef",
        title=title,
        body="Some body content about the concept discussed in the title.",
        tags=[],
        language="en",
        source="kindle",
        source_path="/tmp/note.md",
        created_at="2026-07-21T00:00:00Z",
        modified_at="2026-07-21T00:00:00Z",
        domain=domain,
        word_count=200,
    )


def _mock_response(proposed_page: str, summary: str = "A short concept statement.") -> str:
    return json.dumps({
        "summary": summary,
        "proposed_page": proposed_page,
        "is_new_page": True,
        "link_only": False,
        "proposed_links": [],
        "confidence": 0.8,
        "flag_contradiction": False,
        "flag_duplicate": False,
    })


def test_generate_proposal_no_mid_word_truncation():
    long_slug = "Sprint How to Solve Big Problems and Test New Ideas in Just Five Days"
    with patch("ollama_agent._call_ollama", return_value=_mock_response(long_slug)):
        proposal = generate_proposal(_make_note(), domain="philosophy")
    source_words = {w.lower() for w in long_slug.split()}
    for token in proposal.proposed_page.split("-"):
        assert token in source_words, f"{token!r} is not a whole word from the source phrase"


def test_generate_proposal_strips_domain_suffix():
    with patch("ollama_agent._call_ollama", return_value=_mock_response("tribes-leadership-marketing")):
        proposal = generate_proposal(_make_note(domain="marketing"), domain="marketing")
    assert proposal.proposed_page == "tribes-leadership"


def test_generate_proposal_falls_back_to_title_when_slug_unusable():
    with patch("ollama_agent._call_ollama", return_value=_mock_response("none")):
        proposal = generate_proposal(_make_note(title="Antifragilidade"), domain="philosophy")
    assert proposal.proposed_page == "antifragilidade"


def test_generate_proposal_raises_when_slug_and_title_both_unusable():
    with patch("ollama_agent._call_ollama", return_value=_mock_response("none")):
        with pytest.raises(ValueError):
            generate_proposal(_make_note(title="!!!"), domain="philosophy")
