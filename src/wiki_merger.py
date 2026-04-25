"""
Wiki slug duplicate merger — detects and merges wiki pages that share the same
or near-identical slugs within the same domain, or exact slugs across domains.

Usage:
  python src/wiki_merger.py detect              # report all duplicate groups
  python src/wiki_merger.py merge FILE1 FILE2   # merge specific pages
  python src/wiki_merger.py merge F1 F2 --keep F1
  python src/wiki_merger.py merge F1 F2 --dry-run
  python src/wiki_merger.py batch               # merge all detected groups
  python src/wiki_merger.py batch --dry-run
"""
import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Optional

import yaml


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PageEntry:
    path: Path
    domain: str
    slug: str
    normalized_slug: str
    confidence: float
    sources: list[str]
    links: list[str]
    languages: list[str]
    body: str
    tail: str
    heading: str
    meta: dict


@dataclass
class DuplicateGroup:
    kind: Literal["same-domain", "cross-domain"]
    pages: list[PageEntry]
    canonical: PageEntry
    redundant: list[PageEntry]


@dataclass
class MergeOutcome:
    group: DuplicateGroup
    status: Literal["merged", "skipped", "error"]
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def normalize_slug(slug: str) -> str:
    return re.sub(r"-{2,}", "-", slug).strip("-")


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
        return after_fm[: boundary.start()].strip(), after_fm[boundary.start():]
    return after_fm, ""


def _extract_heading(body: str) -> str:
    for line in body.split("\n"):
        if line.startswith("## "):
            return line
    return ""


def _load_page(path: Path) -> PageEntry:
    content = path.read_text(encoding="utf-8")
    meta = _parse_front_matter(content)
    body, tail = _extract_body_and_tail(content)
    heading = _extract_heading(body)
    domain = path.parent.name
    slug = meta.get("slug", path.stem)
    return PageEntry(
        path=path,
        domain=domain,
        slug=slug,
        normalized_slug=normalize_slug(slug),
        confidence=float(meta.get("confidence", 0.0)),
        sources=list(meta.get("sources") or []),
        links=list(meta.get("links") or []),
        languages=list(meta.get("languages") or []),
        body=body,
        tail=tail,
        heading=heading,
        meta=meta,
    )


def _merge_front_matter(pages: list[PageEntry], canonical: PageEntry) -> dict:
    all_sources = list(dict.fromkeys(s for p in pages for s in p.sources))
    all_links = list(dict.fromkeys(lk for p in pages for lk in p.links))
    all_langs = list(dict.fromkeys(lg for p in pages for lg in p.languages))
    max_confidence = max(p.confidence for p in pages)
    created_vals = [str(p.meta.get("created", "")) for p in pages if p.meta.get("created")]
    min_created = min(created_vals) if created_vals else str(date.today())
    all_disputes = list(dict.fromkeys(d for p in pages for d in (p.meta.get("disputes") or [])))

    meta = dict(canonical.meta)
    meta["slug"] = canonical.slug
    meta["domain"] = canonical.domain
    meta["languages"] = all_langs
    meta["created"] = min_created
    meta["updated"] = str(date.today())
    meta["version"] = int(canonical.meta.get("version", 1)) + 1
    meta["sources"] = all_sources
    meta["links"] = all_links
    meta["disputes"] = all_disputes
    meta["confidence"] = max_confidence
    return meta


def _build_page_content(meta: dict, heading: str, body: str) -> str:
    fm_str = yaml.dump(meta, allow_unicode=True, default_flow_style=False, sort_keys=False)
    body_block = f"{heading}\n\n{body}" if heading else body

    sources_lines = "\n".join(f"- [[{s}]]" for s in meta.get("sources", []))
    links_lines = "\n".join(f"- [[{lk}]]" for lk in meta.get("links", []))

    content = f"---\n{fm_str}---\n\n{body_block}\n\n## Sources\n{sources_lines}\n"
    if meta.get("links"):
        content += f"\n## Related\n{links_lines}\n"
    return content


# ---------------------------------------------------------------------------
# Body consolidation
# ---------------------------------------------------------------------------

def _consolidate_bodies(pages: list[PageEntry], cfg: dict) -> str:
    from wiki_cleaner import _consolidate

    def _paragraphs(body: str) -> list[str]:
        lines = body.split("\n")
        rest = "\n".join(ln for ln in lines if not ln.startswith("## ")).strip()
        return [p.strip() for p in re.split(r"\n{2,}", rest) if p.strip()]

    # Check if all bodies are identical (skip LLM)
    bodies_norm = [p.body.strip().lower() for p in pages]
    if len(set(bodies_norm)) == 1:
        print("[SKIP-LLM] Bodies identical, skipping consolidation")
        return "\n\n".join(_paragraphs(pages[0].body))

    # Collect unique paragraphs across all pages
    seen: set[str] = set()
    unique_paragraphs: list[str] = []
    for p in pages:
        for para in _paragraphs(p.body):
            key = para.strip().lower()
            if key not in seen:
                seen.add(key)
                unique_paragraphs.append(para)

    if not unique_paragraphs:
        return ""
    if len(unique_paragraphs) <= 2:
        return "\n\n".join(unique_paragraphs)

    return _consolidate(unique_paragraphs, cfg)


# ---------------------------------------------------------------------------
# Canonical selection
# ---------------------------------------------------------------------------

def _select_canonical_same_domain(pages: list[PageEntry]) -> PageEntry:
    clean = [p for p in pages if p.slug == p.normalized_slug]
    candidates = clean if clean else pages
    return sorted(candidates, key=lambda p: (-p.confidence, p.slug))[0]


def _select_canonical_cross_domain(pages: list[PageEntry]) -> PageEntry:
    return sorted(pages, key=lambda p: (-p.confidence, p.domain))[0]


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def detect_same_domain_pairs() -> list[DuplicateGroup]:
    from wiki_store import list_all_pages, _wiki_root

    wiki_root = _wiki_root()
    by_domain: dict[str, list[PageEntry]] = {}
    for info in list_all_pages():
        path = wiki_root / "domains" / info["domain"] / f"{info['slug']}.md"
        if not path.exists():
            continue
        try:
            entry = _load_page(path)
        except Exception:
            continue
        by_domain.setdefault(info["domain"], []).append(entry)

    groups: list[DuplicateGroup] = []
    for entries in by_domain.values():
        norm_map: dict[str, list[PageEntry]] = {}
        for e in entries:
            norm_map.setdefault(e.normalized_slug, []).append(e)
        for group_pages in norm_map.values():
            if len({p.slug for p in group_pages}) < 2:
                continue
            canonical = _select_canonical_same_domain(group_pages)
            redundant = [p for p in group_pages if p.slug != canonical.slug]
            groups.append(DuplicateGroup(
                kind="same-domain",
                pages=group_pages,
                canonical=canonical,
                redundant=redundant,
            ))
    return groups


def detect_cross_domain_groups() -> list[DuplicateGroup]:
    from wiki_store import list_all_pages, _wiki_root

    wiki_root = _wiki_root()
    by_slug: dict[str, list[PageEntry]] = {}
    for info in list_all_pages():
        path = wiki_root / "domains" / info["domain"] / f"{info['slug']}.md"
        if not path.exists():
            continue
        try:
            entry = _load_page(path)
        except Exception:
            continue
        by_slug.setdefault(info["slug"], []).append(entry)

    groups: list[DuplicateGroup] = []
    for entries in by_slug.values():
        if len({e.domain for e in entries}) < 2:
            continue
        canonical = _select_canonical_cross_domain(entries)
        redundant = [p for p in entries if not (p.slug == canonical.slug and p.domain == canonical.domain)]
        groups.append(DuplicateGroup(
            kind="cross-domain",
            pages=entries,
            canonical=canonical,
            redundant=redundant,
        ))
    return groups


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------

def _merge_group(group: DuplicateGroup, dry_run: bool, cfg: dict) -> MergeOutcome:
    from wiki_store import write_wiki_page, delete_wiki_page, remove_slug_from_index
    from vector_store import get_vector_store
    from db import get_db

    canonical = group.canonical

    merged_meta = _merge_front_matter(group.pages, canonical)
    consolidated = _consolidate_bodies(group.pages, cfg)

    if not consolidated and any(p.body.strip() for p in group.pages):
        return MergeOutcome(group=group, status="error", error="LLM returned empty body")

    new_content = _build_page_content(merged_meta, canonical.heading, consolidated)

    if dry_run:
        print(f"\n  --- OLD BODY ({canonical.slug}) ---")
        print(f"  {canonical.body[:300]}{'...' if len(canonical.body) > 300 else ''}")
        print(f"\n  --- NEW BODY ({canonical.slug}) ---")
        print(f"  {consolidated[:300]}{'...' if len(consolidated) > 300 else ''}\n")
        return MergeOutcome(group=group, status="merged")

    try:
        write_wiki_page(canonical.domain, canonical.slug, new_content)

        vs = get_vector_store()
        db = get_db()

        for redundant in group.redundant:
            delete_wiki_page(redundant.domain, redundant.slug)
            remove_slug_from_index(redundant.domain, redundant.slug)
            try:
                vs.delete_embedding(redundant.slug, redundant.domain)
            except Exception as e:
                print(f"[WARN] ChromaDB delete failed for {redundant.slug}: {e}")
            try:
                db.clear_wiki_page(redundant.slug)
            except Exception as e:
                print(f"[WARN] SQLite clear failed for {redundant.slug}: {e}")

        try:
            lang = (merged_meta.get("languages") or ["pt"])[0]
            vs.upsert(canonical.slug, consolidated, canonical.domain, lang)
        except Exception as e:
            print(f"[WARN] ChromaDB upsert failed for {canonical.slug}: {e}")

        return MergeOutcome(group=group, status="merged")

    except Exception as e:
        return MergeOutcome(group=group, status="error", error=str(e))


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------

def cmd_detect(_args) -> int:
    same_domain = detect_same_domain_pairs()
    cross_domain = detect_cross_domain_groups()

    if same_domain:
        print("=== Same-Domain Near-Duplicates ===\n")
        for group in same_domain:
            print(f"[{group.canonical.domain}]")
            print(f"  KEEP  {group.canonical.slug:<55} (conf={group.canonical.confidence:.2f})")
            for r in group.redundant:
                print(f"  MERGE {r.slug:<55} (conf={r.confidence:.2f})")
            print()
    else:
        print("=== Same-Domain Near-Duplicates ===\n  (none found)\n")

    if cross_domain:
        print("=== Cross-Domain Slug Groups ===\n")
        for group in sorted(cross_domain, key=lambda g: g.canonical.slug):
            print(f"[{group.canonical.slug}]")
            print(f"  KEEP  {group.canonical.domain:<35} (conf={group.canonical.confidence:.2f})")
            for r in sorted(group.redundant, key=lambda p: p.domain):
                print(f"  MERGE {r.domain:<35} (conf={r.confidence:.2f})")
            print()
    else:
        print("=== Cross-Domain Slug Groups ===\n  (none found)\n")

    print(f"Summary: {len(same_domain)} same-domain pair(s), {len(cross_domain)} cross-domain group(s)")
    return 0


def cmd_merge(args) -> int:
    cfg = _load_settings()
    paths = [Path(f) for f in args.files]

    for p in paths:
        if not p.exists():
            print(f"[ERROR] File not found: {p}", file=sys.stderr)
            return 2

    pages = []
    for p in paths:
        try:
            pages.append(_load_page(p))
        except Exception as e:
            print(f"[ERROR] Could not load {p}: {e}", file=sys.stderr)
            return 2

    domains = {p.domain for p in pages}
    kind: Literal["same-domain", "cross-domain"] = "cross-domain" if len(domains) > 1 else "same-domain"

    if args.keep:
        keep_path = Path(args.keep).resolve()
        canonical = next((p for p in pages if p.path.resolve() == keep_path), None)
        if canonical is None:
            print("[ERROR] --keep path is not among the provided files", file=sys.stderr)
            return 2
    elif kind == "same-domain":
        canonical = _select_canonical_same_domain(pages)
    else:
        canonical = _select_canonical_cross_domain(pages)

    redundant = [p for p in pages if not (p.slug == canonical.slug and p.domain == canonical.domain)]
    group = DuplicateGroup(kind=kind, pages=pages, canonical=canonical, redundant=redundant)

    merged_sources_count = len(list(dict.fromkeys(s for p in pages for s in p.sources)))
    merged_links_count = len(list(dict.fromkeys(lk for p in pages for lk in p.links)))
    print(f"[MERGE] {canonical.slug} ({canonical.domain})")
    print(f"  canonical: {canonical.path}")
    for r in redundant:
        print(f"  deleting:  {r.path}")
    print(f"  sources: {len(canonical.sources)} → {merged_sources_count} (merged)")
    print(f"  links:   {len(canonical.links)} → {merged_links_count} (merged)")
    if len({p.domain for p in pages}) > 1:
        label = "LLM consolidation" if len({p.body.strip().lower() for p in pages}) > 1 else "identical, no LLM"
        print(f"  body: {label}")

    outcome = _merge_group(group, args.dry_run, cfg)

    if outcome.status == "merged":
        prefix = "[DRY-RUN] " if args.dry_run else ""
        print(f"{prefix}[DONE] {canonical.slug}")
        return 0
    elif outcome.status == "error":
        print(f"[ERROR] {outcome.error}", file=sys.stderr)
        return 1
    return 0


def run_batch(dry_run: bool, cfg: dict) -> None:
    sd_found = sd_merged = sd_skipped = sd_errored = 0
    cd_found = cd_merged = cd_skipped = cd_errored = 0

    print("=== Processing Same-Domain Pairs ===\n")
    for group in detect_same_domain_pairs():
        sd_found += 1
        slug = group.canonical.slug
        domain = group.canonical.domain
        print(f"[MERGE] {slug} ({domain}) ... ", end="", flush=True)
        outcome = _merge_group(group, dry_run, cfg)
        if outcome.status == "merged":
            print("[DONE]")
            sd_merged += 1
        elif outcome.status == "skipped":
            print("[SKIP]")
            sd_skipped += 1
        else:
            print(f"[ERROR] {outcome.error}")
            sd_errored += 1

    print("\n=== Processing Cross-Domain Groups ===\n")
    for group in detect_cross_domain_groups():
        cd_found += 1
        slug = group.canonical.slug
        domain = group.canonical.domain
        print(f"[MERGE] {slug} → {domain} ... ", end="", flush=True)
        outcome = _merge_group(group, dry_run, cfg)
        if outcome.status == "merged":
            print("[DONE]")
            cd_merged += 1
        elif outcome.status == "skipped":
            print("[SKIP]")
            cd_skipped += 1
        else:
            print(f"[ERROR] {outcome.error}")
            cd_errored += 1

    prefix = "[DRY-RUN] " if dry_run else ""
    print(f"\n{prefix}Summary:")
    print(f"  Same-domain:  {sd_found} found, {sd_merged} merged, {sd_skipped} skipped, {sd_errored} errored")
    print(f"  Cross-domain: {cd_found} found, {cd_merged} merged, {cd_skipped} skipped, {cd_errored} errored")
    if sd_errored + cd_errored > 0:
        sys.exit(1)


def cmd_batch(args) -> int:
    cfg = _load_settings()
    run_batch(args.dry_run, cfg)
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wiki slug duplicate merger")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("detect", help="Report all duplicate groups without modifying files")

    merge_p = sub.add_parser("merge", help="Merge specific pages into canonical")
    merge_p.add_argument("files", nargs="+", metavar="FILE")
    merge_p.add_argument("--keep", metavar="PATH", help="Force a specific file as canonical")
    merge_p.add_argument("--dry-run", action="store_true")

    batch_p = sub.add_parser("batch", help="Detect and merge all duplicate groups")
    batch_p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if args.command == "detect":
        sys.exit(cmd_detect(args))
    elif args.command == "merge":
        sys.exit(cmd_merge(args))
    elif args.command == "batch":
        sys.exit(cmd_batch(args))
