"""
Parser for Kindle My Clippings.txt — groups highlights per book by domain,
producing one NoteRecord per (book, domain) pair.
"""
import hashlib
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

import yaml

from models import NoteRecord


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug[:80]


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _load_domains() -> dict:
    cfg = _load_settings()
    domains_path = Path(__file__).parent.parent / cfg["domains"]["config_file"]
    with open(domains_path) as f:
        return yaml.safe_load(f)["domains"]


def _merge_thin_groups(
    groups: Dict[str, List[str]],
    domains: dict,
    min_size: int,
) -> Dict[str, List[str]]:
    """
    Single-pass: reassign highlights from thin groups (below min_size) into
    the best-scoring group that already has >= min_size highlights.
    If no large group exists, keep everything in the largest group.
    """
    if not groups:
        return groups

    large = {d: list(h) for d, h in groups.items() if len(h) >= min_size}
    thin = {d: h for d, h in groups.items() if len(h) < min_size}

    if not thin:
        return groups

    if not large:
        # All groups are thin — collapse into the largest one
        largest = max(groups, key=lambda d: len(groups[d]))
        merged: List[str] = []
        for h in groups.values():
            merged.extend(h)
        return {largest: merged}

    # Merge each thin highlight into the best-scoring large group
    from classifier import keyword_classify
    for thin_highlights in thin.values():
        for highlight in thin_highlights:
            scores = {
                d: sum(1 for s in domains[d].get("seeds", []) if s.lower() in highlight.lower())
                for d in large
            }
            best = max(scores, key=lambda k: scores[k])
            large[best].append(highlight)

    return large


class KindleParser:
    """Parse Kindle clippings file into NoteRecords — one per (book, domain)."""

    SEPARATOR = "=========="

    @staticmethod
    def parse_to_records(file_path: Path) -> List[NoteRecord]:
        """
        Parse a Kindle clippings file into NoteRecords.
        Each highlight is classified individually; highlights sharing the same
        primary domain are grouped into a single NoteRecord.
        Books with only one surviving domain group get the bare book title;
        books with multiple groups get a title suffix "[domain]".
        """
        from langdetect import detect, DetectorFactory
        from classifier import keyword_classify

        DetectorFactory.seed = 0

        try:
            raw_bytes = file_path.read_bytes()
            content = raw_bytes.decode("utf-8").lstrip("﻿")
        except Exception:
            return []

        cfg = _load_settings()
        min_group_size = cfg.get("kindle", {}).get("min_group_size", 3)
        domains = _load_domains()

        clippings = content.split(KindleParser.SEPARATOR)

        # Step 1 — Parse: accumulate raw highlights per book
        books: Dict[str, dict] = defaultdict(lambda: {
            "highlights": [], "author": "Unknown",
        })

        for clipping_text in clippings:
            clipping_text = clipping_text.strip()
            if not clipping_text:
                continue
            lines = clipping_text.strip().split("\n")
            if len(lines) < 3:
                continue

            title_line = lines[0].strip()
            author_match = re.search(r"\(([^)]+)\)$", title_line)
            author = author_match.group(1) if author_match else "Unknown"
            book_title = re.sub(r"\s*\([^)]+\)$", "", title_line).strip()

            highlight = "\n".join(lines[2:]).strip()
            if not highlight:
                continue

            books[book_title]["highlights"].append(highlight)
            books[book_title]["author"] = author

        stat = file_path.stat()
        file_modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        records = []

        for book_title, data in books.items():
            highlights = data["highlights"]
            author = data["author"]

            # Step 2 — Classify each highlight individually
            domain_groups: Dict[str, List[str]] = defaultdict(list)
            for highlight in highlights:
                domain = keyword_classify(highlight, domains)
                domain_groups[domain].append(highlight)

            # Step 3 — Merge thin groups
            domain_groups = _merge_thin_groups(dict(domain_groups), domains, min_group_size)

            multi = len(domain_groups) > 1

            # Step 4 — Create one NoteRecord per surviving domain group
            for domain, group_highlights in domain_groups.items():
                body = "\n\n---\n\n".join(group_highlights)
                word_count = len(body.split())
                title = f"{book_title} [{domain}]" if multi else book_title

                try:
                    lang = detect(body[:500]) if body else "unknown"
                    if lang not in ("pt", "en", "fr", "es"):
                        lang = "unknown"
                except Exception:
                    lang = "unknown"

                combined = f"{book_title}\n{domain}\n{body}"
                note_id = hashlib.sha256(combined.encode("utf-8")).hexdigest()

                records.append(NoteRecord(
                    id=note_id,
                    title=title,
                    body=body,
                    tags=[author],
                    language=lang,
                    source="kindle",
                    source_path=f"{file_path.resolve()}#{_slugify(book_title)}#{domain}",
                    created_at=file_modified,
                    modified_at=file_modified,
                    word_count=word_count,
                    domain=domain,
                ))

        return records

    @staticmethod
    def parse_directory_to_records(directory: Path) -> List[NoteRecord]:
        """Parse all Kindle clippings files to NoteRecords."""
        records = []
        for txt_file in directory.glob("**/*.txt"):
            try:
                records.extend(KindleParser.parse_to_records(txt_file))
            except Exception as e:
                print(f"Error parsing {txt_file}: {e}")
        return records
