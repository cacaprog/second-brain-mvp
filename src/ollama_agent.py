"""
Proposal engine for Second Brain v2.
Calls Ollama (Qwen 2.5) with JSON mode to generate wiki integration proposals.
Post-processes the JSON response and determines fast-track eligibility.
"""
import json
import re
import unicodedata
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from models import NoteRecord, Proposal
from wiki_store import read_domain_index, slug_exists_in_index


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


PROPOSAL_PROMPT = """
You are maintaining a Zettelkasten wiki. Propose how a new note should be
integrated — do not invent connections that are not clearly present in the note.

Existing concepts in this domain (index):
{domain_index}

New note:
Title: {title}
Body: {body}
Language: {language}

Rules:
- The proposed_page slug must be 1–4 words, lowercase-hyphenated, max 40 chars (e.g. "antifragilidade", "decisoes-reversiveis").
- Only propose [[wikilinks]] to concepts explicitly listed in the index above.
- If no link is warranted, return an empty proposed_links list.
- Do not hallucinate connections.
- Respond with valid JSON only, no preamble, no markdown fences.
- Write the summary as a direct statement of the concept itself — not as a
  description of the note. NEVER start the summary with any word or phrase that
  refers to the note as an object. Forbidden openings include (but are not limited
  to): "A nota", "A nova nota", "Esta nota", "O texto", "O conteúdo", "The note",
  "This note", "The text". Write as if adding a paragraph to a reference article:
  state the idea, insight, or principle directly in the note's language.

JSON schema:
{{
  "summary": "string (2-3 sentences, same language as note — concept-first, not note-first)",
  "proposed_page": "string (slug: lowercase-hyphenated)",
  "is_new_page": bool,
  "link_only": bool,
  "proposed_links": ["slug1", "slug2"],
  "confidence": float,
  "flag_contradiction": bool,
  "flag_duplicate": bool
}}"""

KNOWLEDGE_CARD_PROMPT = """
You are building a structured knowledge card for a second-brain wiki.
Analyze the article or paper below and produce exactly four Markdown sections.

Article content:
{body}

Section rules:
1. ## Summary — 1-2 sentences describing the main topic and central claim.
2. ## Key Findings OR ## Key Arguments — choose "Key Findings" if the text contains empirical
   signals (results, study, experiment, experiments, data, dataset, findings, methodology, methods);
   otherwise choose "Key Arguments". Write a bullet list of the most important points.
3. ## Core Concepts — bullet list of the central ideas, terms, or frameworks used or introduced.
4. ## Open Questions OR ## Questions Raised — choose "Open Questions" for empirical papers;
   choose "Questions Raised" for opinion/review/explainer articles. Bullet list of gaps,
   limitations, or follow-up questions.

If a section cannot be populated from the content, write exactly:
_(insufficient content — revisit source)_

Do NOT:
- Add extra sections beyond the four listed above.
- Fabricate content that is not present in the article.
- Include markdown fences or any preamble.

Output the four sections and nothing else.
"""

STRICT_SUFFIX = "\nRespond with valid JSON only. No explanation, no markdown fences."


def _slugify(text: str) -> str:
    # Transliterate accented chars (ã→a, ç→c, etc.) before stripping
    normalized = unicodedata.normalize("NFKD", text.lower())
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9\s-]", "", ascii_text)
    slug = re.sub(r"[\s]+", "-", slug.strip())
    return slug[:40]


def _call_ollama(model: str, prompt: str, timeout: int, num_predict: int = 512) -> str:
    import ollama

    def _call():
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            think=False,
            options={"num_predict": num_predict},
        )
        return response["message"]["content"]

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call)
        return future.result(timeout=timeout)


def _parse_json(raw: str) -> dict:
    # Strip <think>...</think> blocks from reasoning models
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # Strip markdown fences
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    # Extract first JSON object if embedded in prose
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)
    return json.loads(raw)


def _is_fast_track(proposal: Proposal, domain: str) -> bool:
    cfg = _load_settings()
    if proposal.link_only:
        threshold = cfg["ingestion"].get(
            "link_only_fast_track_confidence",
            cfg["ingestion"]["fast_track_confidence"],
        )
        return (
            proposal.confidence >= threshold
            and not proposal.flag_contradiction
            and not proposal.flag_duplicate
            and not proposal.is_new_page
        )
    threshold = cfg["ingestion"]["fast_track_confidence"]
    return (
        proposal.confidence >= threshold
        and not proposal.flag_contradiction
        and not proposal.flag_duplicate
        and not proposal.is_new_page
        and all(slug_exists_in_index(domain, link) for link in proposal.proposed_links)
    )


def generate_knowledge_card(note: NoteRecord) -> str:
    """
    Generate a structured four-section knowledge card body for an article note.
    Returns the raw markdown string with four H2 sections.
    Raises ValueError on Ollama failure.
    """
    cfg = _load_settings()
    model = cfg["ollama"]["model"]
    timeout = cfg["ollama"]["timeout_seconds"]
    num_predict = cfg["ollama"].get("num_predict", 4096)

    prompt = KNOWLEDGE_CARD_PROMPT.format(body=note.body[:12000])

    try:
        raw = _call_ollama(model, prompt, timeout, num_predict)
    except FuturesTimeout:
        raise ValueError(f"Ollama timeout after {timeout}s")

    # Strip <think>...</think> blocks from reasoning models
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    return raw


def generate_proposal(note: NoteRecord, domain: str) -> Optional[Proposal]:
    """
    Generate a wiki integration proposal for note using Ollama.
    Returns None on unrecoverable failure (error already logged by caller).
    Raises ValueError if the note should be sent to the errors table.
    """
    cfg = _load_settings()
    model = cfg["ollama"]["model"]
    timeout = cfg["ollama"]["timeout_seconds"]
    min_confidence = cfg["ollama"]["min_confidence"]
    link_only_threshold = cfg["ingestion"]["link_only_word_threshold"]
    num_predict = cfg["ollama"].get("num_predict", 4096)

    _INVALID_SLUGS_SET = {"none", "null", "untitled", "no-proposal", "no-concept", "unknown", "n-a"}
    raw_index = read_domain_index(domain)
    # Strip any rows whose slug column matches an invalid slug so the model
    # cannot select them as targets.
    domain_index = "\n".join(
        line for line in raw_index.splitlines()
        if not any(f"| {s} |" in line for s in _INVALID_SLUGS_SET)
    )
    prompt = PROPOSAL_PROMPT.format(
        domain_index=domain_index,
        title=note.title,
        body=note.body[:12000],  # guard against very large notes
        language=note.language,
    )

    raw_json = None
    for attempt in range(2):
        try:
            p = prompt if attempt == 0 else prompt + STRICT_SUFFIX
            raw_json = _call_ollama(model, p, timeout, num_predict)
            data = _parse_json(raw_json)
            break
        except FuturesTimeout:
            raise ValueError(f"Ollama timeout after {timeout}s")
        except (json.JSONDecodeError, ValueError) as e:
            if attempt == 1:
                raise ValueError(f"JSON parse failed after retry: {e}")
            # Will retry with stricter suffix

    if raw_json is None:
        raise ValueError("No response from Ollama")

    # Extract and validate fields
    summary = str(data.get("summary", "")).strip()
    if not summary:
        raise ValueError("Empty summary in proposal")

    _NOTE_FIRST_PREFIXES = (
        "a nota", "a nova nota", "esta nota", "esse texto", "o texto",
        "o conteúdo", "o artigo", "the note", "this note", "the text",
    )
    if any(summary.lower().startswith(p) for p in _NOTE_FIRST_PREFIXES):
        raise ValueError(f"Summary uses note-first phrasing: {summary[:60]!r}")

    _INVALID_SLUGS = {"none", "null", "untitled", "no-proposal", "no-concept", "unknown", "n-a"}
    proposed_page_raw = str(data.get("proposed_page", note.title))
    proposed_page = _slugify(proposed_page_raw)
    if not proposed_page or proposed_page in _INVALID_SLUGS:
        proposed_page = _slugify(note.title)
    if not proposed_page or proposed_page in _INVALID_SLUGS:
        raise ValueError(f"LLM returned invalid slug {proposed_page_raw!r} and note title also unusable")

    is_new_page = bool(data.get("is_new_page", True))
    link_only = bool(data.get("link_only", False))
    confidence = float(max(0.0, min(1.0, data.get("confidence", 0.5))))
    flag_contradiction = bool(data.get("flag_contradiction", False))
    flag_duplicate = bool(data.get("flag_duplicate", False))

    raw_links = data.get("proposed_links", [])
    if not isinstance(raw_links, list):
        raw_links = []

    # Strip invalid links (not in domain index, or self-referential) and penalise
    valid_links = []
    stripped = 0
    for link in raw_links:
        link = _slugify(str(link))
        if link and link != proposed_page and slug_exists_in_index(domain, link):
            valid_links.append(link)
        else:
            stripped += 1
    confidence = max(0.0, confidence - 0.1 * stripped)

    # link_only override: cannot apply to new pages
    if is_new_page:
        link_only = False

    # Auto-set link_only for short notes targeting an existing page
    if note.word_count < link_only_threshold and not is_new_page:
        link_only = True

    if confidence < min_confidence:
        raise ValueError(
            f"Confidence {confidence:.2f} below minimum {min_confidence}"
        )

    proposal = Proposal(
        id=str(uuid.uuid4()),
        note_id=note.id,
        note_version=note.version,
        proposed_page=proposed_page,
        is_new_page=is_new_page,
        link_only=link_only,
        summary=summary,
        proposed_links=valid_links,
        confidence=confidence,
        flag_contradiction=flag_contradiction,
        flag_duplicate=flag_duplicate,
        fast_track_eligible=False,  # set below
        ollama_model=model,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    proposal.fast_track_eligible = _is_fast_track(proposal, domain)
    return proposal
