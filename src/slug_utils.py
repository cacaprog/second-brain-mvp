"""
Shared slug-shaping utilities used by both note-ingestion generation
(ollama_agent.py) and the retroactive wiki slug migration (slug_migrator.py).
"""
import re
import unicodedata

PLACEHOLDER_SLUGS = {"none", "null", "untitled", "no-proposal", "no-concept", "unknown", "n-a"}

# Connector/filler words that read as a dangling fragment if left at the very
# end of a slug (e.g. truncating "value-in-use-vs-value-in-exchange" to 4 words
# naively yields "value-in-use-vs"). Only the trailing word is ever checked —
# these are common enough mid-slug that stripping them everywhere would be wrong.
_TRAILING_STOPWORDS = {
    "vs", "to", "of", "and", "or", "the", "a", "an", "in", "on", "at", "by",
    "for", "with", "from", "that", "this", "is", "are", "as",
    "de", "da", "do", "das", "dos", "e", "o", "que", "com", "para", "em", "um", "uma",
}


def slugify(text: str, max_words: int = 4) -> str:
    """Lowercase, transliterate, hyphenate, and word-boundary-truncate text into a slug.

    Never slices inside a word — truncation happens on word count, not character
    count, so a slug can never end mid-token the way the old slug[:40] approach did.
    A trailing connector/filler word (see _TRAILING_STOPWORDS) is dropped so the
    result never ends on a dangling fragment like "...-vs" or "...-to".
    """
    normalized = unicodedata.normalize("NFKD", text.lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9\s-]", "", ascii_text)
    slug = re.sub(r"[\s-]+", "-", slug.strip())
    slug = slug.strip("-")
    if not slug:
        return ""
    words = slug.split("-")[:max_words]
    while len(words) > 1 and words[-1] in _TRAILING_STOPWORDS:
        words = words[:-1]
    return "-".join(words)


def is_placeholder(slug: str) -> bool:
    """True if slug is empty or a known unusable placeholder value."""
    return not slug or slug in PLACEHOLDER_SLUGS


def strip_domain_suffix(slug: str, domain: str) -> str:
    """Strip a trailing "-{domain}" segment from slug, if present."""
    suffix = f"-{domain}"
    if slug.endswith(suffix) and slug != domain:
        return slug[: -len(suffix)]
    return slug
