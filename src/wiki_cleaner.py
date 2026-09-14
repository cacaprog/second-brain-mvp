"""
Wiki note body consolidation — collapses repetitive paragraphs into a single
coherent synthesis using the configured Ollama model.

Usage:
  python src/wiki_cleaner.py                   # batch: all wiki pages
  python src/wiki_cleaner.py --dry-run         # preview only, no writes
  python src/wiki_cleaner.py --path FILEPATH   # single page
"""
import argparse
import re
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from datetime import date
from pathlib import Path

import yaml

from db import get_db

CONSOLIDATION_PROMPT = """\
Below are multiple paragraphs about the same concept, written in slightly \
different phrasings across separate ingestion rounds. They contain significant \
overlap and repetition.

Consolidate them into a single coherent paragraph (or 2-3 paragraphs only if \
the concepts are genuinely distinct and non-overlapping). Write in the same \
language as the input. Do not add new information. Do not refer to "the note" \
or "the text" — write as a direct statement of the concept, as if adding a \
paragraph to a reference article.

Return only the consolidated text, no preamble, no headings, no markdown fences.

Paragraphs:
{paragraphs}
"""


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _parse_front_matter(content: str) -> dict:
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def _extract_body_and_tail(content: str) -> tuple[str, str]:
    after_fm = re.sub(r"^---\n.*?\n---\n*", "", content, count=1, flags=re.DOTALL).strip()
    boundary = re.search(r"^## (?:Sources|Related)\b", after_fm, re.MULTILINE)
    if boundary:
        return after_fm[: boundary.start()].strip(), after_fm[boundary.start() :]
    return after_fm, ""


def _extract_heading_and_paragraphs(body: str) -> tuple[str, list[str]]:
    heading = ""
    rest_lines = []
    for line in body.split("\n"):
        if line.startswith("## ") and not heading:
            heading = line
        else:
            rest_lines.append(line)
    rest = "\n".join(rest_lines).strip()
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", rest) if p.strip()]
    return heading, paragraphs


def _call_ollama(prompt: str, cfg: dict) -> str:
    import ollama

    def _call():
        response = ollama.chat(
            model=cfg["ollama"]["model"],
            messages=[{"role": "user", "content": prompt}],
            think=False,
            options={"num_predict": 400},
        )
        return response["message"]["content"]

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_call)
        return future.result(timeout=cfg["ollama"]["timeout_seconds"])


def _deduplicate_paragraphs(paragraphs: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for p in paragraphs:
        key = p.strip().lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def _is_article_page(slug: str, db) -> bool:
    note_ids = db.get_notes_by_wiki_page(slug)
    for note_id in note_ids:
        note = db.get_note(note_id)
        if note and note.note_type == "article":
            return True
    return False


def _consolidate(paragraphs: list[str], cfg: dict) -> str:
    numbered = "\n\n".join(f"[{i + 1}] {p}" for i, p in enumerate(paragraphs))
    raw = _call_ollama(CONSOLIDATION_PROMPT.format(paragraphs=numbered), cfg)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = re.sub(r"```[^\n]*\n?", "", raw)
    return raw.strip()


def _rebuild_page(meta: dict, heading: str, consolidated: str, tail: str) -> str:
    meta["updated"] = str(date.today())
    fm_str = yaml.dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False)
    body_block = f"{heading}\n\n{consolidated}" if heading else consolidated
    page = f"---\n{fm_str}---\n\n{body_block}\n"
    if tail:
        page += f"\n{tail}"
    return page


def _process_page(path: Path, dry_run: bool, cfg: dict, db) -> str:
    content = path.read_text(encoding="utf-8")
    meta = _parse_front_matter(content)
    body, tail = _extract_body_and_tail(content)
    heading, paragraphs = _extract_heading_and_paragraphs(body)

    if len(paragraphs) <= 2:
        return "skipped_short"

    slug = meta.get("slug", path.stem)

    if _is_article_page(slug, db):
        print(f"[SKIP-ARTICLE] {slug}")
        return "skipped_article"

    unique = _deduplicate_paragraphs(paragraphs)

    if len(unique) == len(paragraphs):
        print(f"[SKIP-NO-REP] {slug} ({len(paragraphs)} unique paragraphs, composite knowledge)")
        return "skipped_no_rep"

    if len(unique) <= 2:
        new_body = "\n\n".join(unique)
        if dry_run:
            print(f"\n  --- OLD ({slug}) ---")
            print(f"  {body}\n")
            print(f"  --- NEW ({slug}) ---")
            print(f"  {(heading + chr(10) + chr(10) + new_body).strip() if heading else new_body}\n")
            return "deduped"
        new_content = _rebuild_page(meta, heading, new_body, tail)
        path.write_text(new_content, encoding="utf-8")
        print(f"[DEDUPED] {slug} ({len(paragraphs)} → {len(unique)} paragraphs, no LLM)")
        return "deduped"

    print(f"[CONSOLIDATE] {slug} ({len(paragraphs)} paragraphs, {len(unique)} unique → LLM)")

    try:
        consolidated = _consolidate(unique, cfg)
    except FuturesTimeout:
        print(f"[ERROR] {slug}: Ollama timed out")
        return "error"
    except Exception as e:
        print(f"[ERROR] {slug}: {e}")
        return "error"

    if not consolidated:
        print(f"[ERROR] {slug}: empty response, skipping write")
        return "error"

    if dry_run:
        print(f"\n  --- OLD ({slug}) ---")
        print(f"  {body}\n")
        print(f"  --- NEW ({slug}) ---")
        print(f"  {(heading + chr(10) + chr(10) + consolidated).strip() if heading else consolidated}\n")
        return "consolidated"

    new_content = _rebuild_page(meta, heading, consolidated, tail)
    path.write_text(new_content, encoding="utf-8")
    print(f"[DONE] {slug}")
    return "consolidated"


def run(target_path: Path | None, dry_run: bool) -> None:
    cfg = _load_settings()
    wiki_root = Path(__file__).parent.parent / cfg["paths"]["wiki"]
    db = get_db()

    pages: list[Path]
    if target_path:
        pages = [target_path]
    else:
        pages = sorted(p for p in wiki_root.glob("domains/*/*.md") if p.name != "index.md")

    scanned = consolidated = deduped = skipped_short = skipped_article = skipped_no_rep = errored = 0
    for page in pages:
        scanned += 1
        result = _process_page(page, dry_run, cfg, db)
        if result == "consolidated":
            consolidated += 1
        elif result == "deduped":
            deduped += 1
        elif result == "skipped_short":
            skipped_short += 1
        elif result == "skipped_article":
            skipped_article += 1
        elif result == "skipped_no_rep":
            skipped_no_rep += 1
        else:
            errored += 1

    prefix = "[DRY-RUN] " if dry_run else ""
    print(
        f"\n{prefix}Summary: {scanned} scanned"
        f" | consolidated (LLM): {consolidated}"
        f" | deduped (no LLM): {deduped}"
        f" | skipped (≤2 para): {skipped_short}"
        f" | skipped (article): {skipped_article}"
        f" | skipped (no rep): {skipped_no_rep}"
        f" | errors: {errored}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Consolidate repetitive wiki page bodies")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--path", type=Path, metavar="FILE", help="Process a single wiki page")
    args = parser.parse_args()

    if args.path and not args.path.exists():
        print(f"[ERROR] File not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    run(args.path, args.dry_run)
