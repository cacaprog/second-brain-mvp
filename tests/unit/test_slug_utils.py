"""
Unit tests for slug_utils.py — slugify, is_placeholder, strip_domain_suffix.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from slug_utils import is_placeholder, slugify, strip_domain_suffix


# ---------------------------------------------------------------------------
# slugify — word-boundary truncation
# ---------------------------------------------------------------------------

def test_slugify_never_truncates_mid_word():
    long_title = "Sprint How to Solve Big Problems and Test New Ideas in Just Five Days"
    result = slugify(long_title)
    # Every token in the result must appear as a whole word in the source title
    source_words = {w.lower() for w in long_title.split()}
    for token in result.split("-"):
        assert token in source_words, f"{token!r} is not a whole word from the source title"


def test_slugify_caps_at_max_words_default():
    result = slugify("one two three four five six seven")
    assert len(result.split("-")) <= 4


def test_slugify_caps_at_custom_max_words():
    result = slugify("one two three four five six seven", max_words=2)
    assert len(result.split("-")) <= 2


def test_slugify_no_artifact_from_colon_title():
    result = slugify("Ciência e Fé: A Partícula de Deus")
    assert "--" not in result
    assert not result.startswith("-")
    assert not result.endswith("-")


def test_slugify_no_artifact_from_dash_title():
    result = slugify("Semana 3 - Os Anos Iniciais")
    assert "--" not in result
    assert not result.startswith("-")
    assert not result.endswith("-")


def test_slugify_transliterates_accents():
    assert slugify("característica") == "caracteristica"
    assert slugify("automação") == "automacao"


def test_slugify_empty():
    assert slugify("") == ""


def test_slugify_only_special_chars():
    assert slugify("!!! ???") == ""


# ---------------------------------------------------------------------------
# is_placeholder
# ---------------------------------------------------------------------------

def test_is_placeholder_empty_string():
    assert is_placeholder("") is True


def test_is_placeholder_none_literal():
    assert is_placeholder("none") is True


def test_is_placeholder_denylist_entries():
    for bad in ("null", "untitled", "no-proposal", "no-concept", "unknown", "n-a"):
        assert is_placeholder(bad) is True


def test_is_placeholder_good_slug():
    assert is_placeholder("antifragilidade") is False
    assert is_placeholder("statistical-thinking") is False


# ---------------------------------------------------------------------------
# strip_domain_suffix
# ---------------------------------------------------------------------------

def test_strip_domain_suffix_removes_trailing_domain():
    result = strip_domain_suffix("tribes-leadership-marketing", "marketing")
    assert result == "tribes-leadership"


def test_strip_domain_suffix_no_match_unchanged():
    result = strip_domain_suffix("antifragilidade", "philosophy")
    assert result == "antifragilidade"


def test_strip_domain_suffix_domain_not_a_suffix():
    # Domain word present but not as a trailing segment — must not be stripped
    result = strip_domain_suffix("marketing-strategy-basics", "marketing")
    assert result == "marketing-strategy-basics"
