"""
Retroactive wiki slug quality migration — re-evaluates existing wiki page
slugs against the same quality rules used at generation time, regenerates
the bad ones, and applies the rename atomically across the wiki files,
SQLite, and ChromaDB.

Usage:
  python src/slug_migrator.py detect                # report all candidates (read-only)
  python src/slug_migrator.py detect --path FILEPATH
  python src/slug_migrator.py apply                 # perform the migration
  python src/slug_migrator.py apply --dry-run
  python src/slug_migrator.py apply --path FILEPATH
"""
import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

import wiki_store
from db import get_db
from ollama_agent import _call_ollama
from slug_utils import is_placeholder, slugify, strip_domain_suffix
from vector_store import get_vector_store

MAX_SLUG_LEN = 40
MAX_SLUG_WORDS = 4

REGEN_PROMPT = """\
You are naming a single wiki page in a personal knowledge base. Read the page
content below and identify the ONE core concept, method, or idea it is about.

Page content:
{body}

Return ONLY a short concept slug: 1-4 lowercase-hyphenated words naming that
core idea. Rules:
- Do NOT just shorten, truncate, or reuse a run of words from a long heading,
  sentence, or instructional phrase you see in the content — read the actual
  content and name the underlying concept in your own words instead.
- If the content contrasts two things (e.g. "X vs Y"), name the general
  principle or phenomenon being illustrated, not a cut-off list of the two things.
- Never end the slug on a connector or filler word (to, vs, of, and, the, a, e, de, ...) —
  every word must be a meaningful standalone term.
- Use only real, correctly-spelled words in the same language as the content.
  Never invent or garble a word.
- Do not include the domain name "{domain}". Do not include punctuation other
  than hyphens.

Respond with the slug only, no preamble, no quotes, no markdown fences.
"""


@dataclass
class MigrationCandidate:
    domain: str
    old_slug: str
    new_slug: Optional[str] = None
    reasons: list = field(default_factory=list)
    status: str = "pending"  # pending | renamed | dry-run | collision | error
    error: Optional[str] = None
    title: str = ""


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Heuristic scan
# ---------------------------------------------------------------------------

def _heuristic_reasons(slug: str, domain: str) -> list:
    reasons = []
    if len(slug) >= MAX_SLUG_LEN:
        reasons.append("length>=40")
    if len(slug.split("-")) > MAX_SLUG_WORDS:
        reasons.append("words>4")
    if "--" in slug:
        reasons.append("artifact--")
    if slug.endswith(f"-{domain}"):
        reasons.append("domain-suffix")
    return reasons


def _already_migrated_slugs() -> set:
    """Slugs that are already the target of a prior `rename:` commit in the wiki's
    own git history (the format wiki_store.rename_wiki_page() produces) — reused
    to make the migration idempotent without any new persisted state."""
    wiki_root = wiki_store._wiki_root()
    try:
        result = subprocess.run(
            ["git", "-C", str(wiki_root), "log", "--oneline"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()

    migrated = set()
    for line in result.stdout.splitlines():
        if " rename: " not in line:
            continue
        try:
            _, rest = line.split(" rename: ", 1)
            _, new_slug = rest.split(" → ", 1)
            migrated.add(new_slug.strip())
        except ValueError:
            continue
    return migrated


def _flag_candidates() -> list:
    already_migrated = _already_migrated_slugs()
    candidates = []
    for page in wiki_store.list_all_pages():
        domain = page["domain"]
        slug = page["slug"]
        if domain == "queries":
            continue
        if slug in already_migrated:
            continue
        reasons = _heuristic_reasons(slug, domain)
        if reasons:
            candidates.append(MigrationCandidate(domain=domain, old_slug=slug, reasons=reasons))
    return candidates


# ---------------------------------------------------------------------------
# Regeneration
# ---------------------------------------------------------------------------

_GENERIC_HEADINGS = {
    "summary", "key findings", "key arguments", "core concepts",
    "open questions", "questions raised",
}


def _strip_front_matter(content: str) -> str:
    return re.sub(r"^---\n.*?\n---\n*", "", content, count=1, flags=re.DOTALL)


def _extract_title(content: str) -> str:
    """Best-effort concept title from a page's first heading.

    Knowledge-card pages (note_type article/rich_note) always open with one of
    a fixed set of structural section headings (## Summary, ## Key Findings,
    ...) rather than a title — those are skipped so callers get "" instead of
    a misleading generic word.
    """
    body = _strip_front_matter(content)
    for line in body.split("\n"):
        if line.startswith("## "):
            heading = line[3:].strip()
            if heading.lower() not in _GENERIC_HEADINGS:
                return heading
    return ""


def _extract_language(content: str) -> str:
    meta = wiki_store._parse_front_matter(content)
    languages = meta.get("languages") or ["pt"]
    return languages[0]


def _regenerate_slug(candidate: MigrationCandidate, page_content: str) -> str:
    cfg = _load_settings()
    model = cfg["ollama"]["model"]
    timeout = cfg["ollama"]["timeout_seconds"]
    num_predict = cfg["ollama"].get("num_predict", 512)

    body = _strip_front_matter(page_content)[:4000]
    prompt = REGEN_PROMPT.format(body=body, domain=candidate.domain)
    raw = _call_ollama(model, prompt, timeout, num_predict)

    new_slug = slugify(raw.strip())
    if is_placeholder(new_slug):
        new_slug = slugify(candidate.title or candidate.old_slug)
    new_slug = strip_domain_suffix(new_slug, candidate.domain)
    return new_slug


def _build_candidates(path_filter: Optional[str] = None) -> list:
    candidates = _flag_candidates()
    if path_filter:
        target_slug = Path(path_filter).stem
        candidates = [c for c in candidates if c.old_slug == target_slug]

    total = len(candidates)
    print(f"{total} page(s) flagged — regenerating slugs (this calls the local LLM once per page, so it can take a while):\n")
    for i, c in enumerate(candidates, 1):
        reason_str = ", ".join(c.reasons)
        print(f"  [{i}/{total}] [{c.domain}] {c.old_slug} ({reason_str}) ... ", end="", flush=True)
        try:
            page_content = wiki_store.read_wiki_page(c.domain, c.old_slug) or ""
            c.title = _extract_title(page_content) or c.old_slug
            c.new_slug = _regenerate_slug(c, page_content)
            if c.new_slug == c.old_slug:
                c.status = "unchanged"
                print("(unchanged — regenerated slug matched the current one)")
            else:
                print(f"→ {c.new_slug}")
        except Exception as e:
            c.status = "error"
            c.error = f"regeneration failed: {e}"
            print(f"ERROR: {e}")

    _resolve_collisions([c for c in candidates if c.status == "pending"])
    return candidates


# ---------------------------------------------------------------------------
# Collision resolution
# ---------------------------------------------------------------------------

def _disambiguate(candidate: MigrationCandidate, taken: set) -> bool:
    """Try to give `candidate` a slug distinct from everything in `taken`, via a
    second word from its own title. Returns True if resolved, False otherwise
    (candidate.status is set to "collision" in that case)."""
    existing_words = set(candidate.new_slug.split("-"))
    extra_words = [
        w for w in slugify(candidate.title, max_words=10).split("-")
        if w and w not in existing_words
    ]
    if extra_words:
        words = candidate.new_slug.split("-") + extra_words[:1]
        candidate_slug = "-".join(words[: MAX_SLUG_WORDS + 1])
        if candidate_slug not in taken:
            candidate.new_slug = candidate_slug
            return True
    candidate.status = "collision"
    return False


def _resolve_collisions(candidates: list) -> None:
    """Ensure every candidate's new_slug is unique within its domain — both
    against sibling candidates in this same batch AND against pages that
    already exist on disk and are not themselves being renamed."""
    by_domain: dict = {}
    for c in candidates:
        by_domain.setdefault(c.domain, []).append(c)

    for domain, group in by_domain.items():
        own_old_slugs = {c.old_slug for c in group}
        taken = set(wiki_store.list_domain_slugs(domain)) - own_old_slugs
        for c in group:
            if c.new_slug in taken:
                if not _disambiguate(c, taken):
                    continue
            taken.add(c.new_slug)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------

def _log_error(candidate: MigrationCandidate, message: str) -> None:
    try:
        db = get_db()
        note_ids = db.get_notes_by_wiki_page(candidate.old_slug)
        if note_ids:
            db.log_error(note_ids[0], "slug_migration", message)
    except Exception:
        pass


def _apply_candidate(candidate: MigrationCandidate, dry_run: bool) -> None:
    if candidate.status != "pending":
        return
    if dry_run:
        candidate.status = "dry-run"
        return

    try:
        wiki_store.rename_wiki_page(candidate.domain, candidate.old_slug, candidate.new_slug)
    except Exception as e:
        candidate.status = "error"
        candidate.error = str(e)
        _log_error(candidate, f"wiki rename failed: {e}")
        return

    try:
        get_db().rename_wiki_page(candidate.old_slug, candidate.new_slug)
    except Exception as e:
        candidate.status = "error"
        candidate.error = str(e)
        _log_error(candidate, f"db rename failed: {e}")
        return

    try:
        content = wiki_store.read_wiki_page(candidate.domain, candidate.new_slug) or ""
        language = _extract_language(content)
        vs = get_vector_store()
        vs.delete_embedding(candidate.old_slug, candidate.domain)
        vs.upsert(candidate.new_slug, content, candidate.domain, language)
    except Exception as e:
        candidate.status = "error"
        candidate.error = str(e)
        _log_error(candidate, f"vector store update failed: {e}")
        return

    candidate.status = "renamed"


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_detect(args) -> int:
    candidates = _build_candidates(path_filter=getattr(args, "path", None))

    renamed = [c for c in candidates if c.status == "pending"]
    collisions = [c for c in candidates if c.status == "collision"]
    errors = [c for c in candidates if c.status == "error"]
    unchanged = [c for c in candidates if c.status == "unchanged"]

    print(f"\n{len(renamed)} will be renamed, {len(collisions)} flagged as needs-manual-review"
          + (f", {len(unchanged)} left unchanged (no better slug found)" if unchanged else "")
          + (f", {len(errors)} errored" if errors else "") + ".")
    print("Run `python src/slug_migrator.py apply` to perform these renames.")
    return 0


def cmd_apply(args) -> int:
    dry_run = getattr(args, "dry_run", False)
    candidates = _build_candidates(path_filter=getattr(args, "path", None))

    to_apply = [c for c in candidates if c.status == "pending"]
    prefix = "[DRY-RUN] " if dry_run else ""
    print()
    for i, c in enumerate(to_apply, 1):
        _apply_candidate(c, dry_run=dry_run)
        label = "OK" if c.status in ("renamed", "dry-run") else c.status
        print(f"{prefix}[{i}/{len(to_apply)}] {c.old_slug} → {c.new_slug}  {label}", flush=True)

    renamed = sum(1 for c in candidates if c.status in ("renamed", "dry-run"))
    errors = [c for c in candidates if c.status == "error"]
    collisions = [c for c in candidates if c.status == "collision"]

    print(f"\nSummary: {renamed} renamed, {len(errors)} error, {len(collisions)} needs-manual-review.")
    if errors:
        print("\nErrors:")
        for c in errors:
            print(f"  [{c.domain}] {c.old_slug}: {c.error}")
    if collisions:
        print("\nNeeds manual review (unresolved collision):")
        for c in collisions:
            print(f"  [{c.domain}] {c.old_slug}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Retroactive wiki slug quality migration")
    sub = parser.add_subparsers(dest="command", required=True)

    detect_p = sub.add_parser("detect", help="Preview slug renames (read-only)")
    detect_p.add_argument("--path", help="Limit to a single wiki page")

    apply_p = sub.add_parser("apply", help="Perform slug renames")
    apply_p.add_argument("--path", help="Limit to a single wiki page")
    apply_p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if args.command == "detect":
        sys.exit(cmd_detect(args))
    elif args.command == "apply":
        sys.exit(cmd_apply(args))
