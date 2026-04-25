"""
Wiki file I/O for Second Brain v2.
Reads and writes wiki markdown pages, manages domain indexes and cross-links.
All git operations go through this module's git_commit_wiki().
"""
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional

import yaml


def _load_settings() -> dict:
    cfg_path = Path(__file__).parent.parent / "config" / "settings.yaml"
    with open(cfg_path) as f:
        return yaml.safe_load(f)


def _wiki_root() -> Path:
    return Path(__file__).parent.parent / _load_settings()["paths"]["wiki"]


def _domain_dir(domain: str) -> Path:
    return _wiki_root() / "domains" / domain


def _page_path(domain: str, slug: str) -> Path:
    return _domain_dir(domain) / f"{slug}.md"


def _index_path(domain: str) -> Path:
    return _domain_dir(domain) / "index.md"


def _cross_links_path() -> Path:
    return _wiki_root() / "cross-links.md"


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def read_domain_index(domain: str) -> str:
    """Return the full text of wiki/domains/{domain}/index.md."""
    idx = _index_path(domain)
    if not idx.exists():
        return "| Slug | Description | Languages |\n|------|-------------|-----------|"
    return idx.read_text(encoding="utf-8")


def read_wiki_page(domain: str, slug: str) -> Optional[str]:
    """Return wiki page content or None if not found."""
    p = _page_path(domain, slug)
    return p.read_text(encoding="utf-8") if p.exists() else None


def read_wiki_page_by_slug(slug: str) -> Optional[str]:
    """Scan all domains to find a page by slug."""
    wiki = _wiki_root()
    for page in wiki.glob(f"domains/*/{slug}.md"):
        return page.read_text(encoding="utf-8")
    return None


def wiki_page_exists(domain: str, slug: str) -> bool:
    return _page_path(domain, slug).exists()


def list_all_pages() -> list[dict]:
    """Return all wiki pages across all domains with slug, domain, and front-matter fields."""
    wiki = _wiki_root()
    results = []
    for page in wiki.glob("domains/*/*.md"):
        if page.name == "index.md":
            continue
        domain = page.parent.name
        slug = page.stem
        meta = _parse_front_matter(page.read_text(encoding="utf-8"))
        results.append({
            "slug": slug,
            "domain": domain,
            "updated": meta.get("updated", ""),
            "confidence": meta.get("confidence", 0.0),
            "sources": meta.get("sources", []),
            "links": meta.get("links", []),
            "languages": meta.get("languages", []),
        })
    return results


def list_domain_slugs(domain: str) -> list[str]:
    """Return all page slugs in a domain."""
    d = _domain_dir(domain)
    if not d.exists():
        return []
    return [p.stem for p in d.glob("*.md") if p.name != "index.md"]


def slug_exists_in_index(domain: str, slug: str) -> bool:
    """Check if a slug appears in the domain index table."""
    idx = read_domain_index(domain)
    return f"| {slug} |" in idx or f"|{slug}|" in idx


# ---------------------------------------------------------------------------
# Write operations (all idempotent)
# ---------------------------------------------------------------------------

def write_wiki_page(domain: str, slug: str, content: str) -> Path:
    """Write (overwrite) a wiki page. Returns the path written."""
    d = _domain_dir(domain)
    d.mkdir(parents=True, exist_ok=True)
    p = _page_path(domain, slug)
    p.write_text(content, encoding="utf-8")
    return p


def update_domain_index(domain: str, slug: str, description: str, languages: list[str] | None = None) -> None:
    """Upsert a row in the domain index table."""
    langs = ", ".join(languages or [])
    new_row = f"| {slug} | {description} | {langs} |"
    idx = _index_path(domain)
    _domain_dir(domain).mkdir(parents=True, exist_ok=True)

    if not idx.exists():
        idx.write_text(
            f"| Slug | Description | Languages |\n|------|-------------|-----------|\n{new_row}\n",
            encoding="utf-8",
        )
        return

    content = idx.read_text(encoding="utf-8")
    lines = content.splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if re.match(rf"^\|\s*{re.escape(slug)}\s*\|", line):
            new_lines.append(new_row)
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(new_row)
    idx.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def remove_slug_from_index(domain: str, slug: str) -> None:
    """Remove a slug's row from the domain index table. No-op if not found."""
    idx = _index_path(domain)
    if not idx.exists():
        return
    content = idx.read_text(encoding="utf-8")
    lines = content.splitlines()
    new_lines = [line for line in lines if not re.match(rf"^\|\s*{re.escape(slug)}\s*\|", line)]
    if len(new_lines) != len(lines):
        idx.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def delete_wiki_page(domain: str, slug: str) -> None:
    """Delete a wiki page file from disk. No-op if not found."""
    p = _page_path(domain, slug)
    if p.exists():
        p.unlink()


def register_cross_link(source: str, target: str) -> None:
    """Upsert a cross-domain link entry in wiki/cross-links.md."""
    cl = _cross_links_path()
    entry = f"| {source} | {target} |"
    if cl.exists():
        content = cl.read_text(encoding="utf-8")
        if entry in content:
            return
        cl.write_text(content.rstrip("\n") + "\n" + entry + "\n", encoding="utf-8")
    else:
        cl.write_text(
            f"| Source | Target |\n|--------|--------|\n{entry}\n",
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------

def git_commit_wiki(page_path: Path, slug: str, confidence: float, model: str) -> str:
    """Stage and commit a wiki page. Returns the git commit hash."""
    wiki = str(_wiki_root())
    rel = str(page_path.relative_to(_wiki_root()))
    subprocess.run(["git", "-C", wiki, "add", rel], check=True)

    # Also stage the domain index and cross-links — use specific paths to avoid
    # sweeping up unrelated working-tree changes (e.g. from wiki_merger runs).
    domain_dir = str(page_path.parent.relative_to(_wiki_root()))
    for extra in [f"{domain_dir}/index.md", "cross-links.md"]:
        try:
            subprocess.run(
                ["git", "-C", wiki, "add", extra],
                check=True, capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass

    msg = f"ingest: {slug} (confidence={confidence:.2f}, model={model})"
    subprocess.run(["git", "-C", wiki, "commit", "-m", msg], check=True)

    result = subprocess.run(
        ["git", "-C", wiki, "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def revert_wiki_commit(git_hash: str) -> None:
    """Revert a wiki commit (for retroactive fast-track rejection)."""
    wiki = str(_wiki_root())
    subprocess.run(
        ["git", "-C", wiki, "revert", "--no-edit", git_hash],
        check=True,
    )


def rename_wiki_page(domain: str, old_slug: str, new_slug: str) -> None:
    """
    Atomically rename a wiki page:
      1. git mv the file
      2. Update slug field in the page's own front matter
      3. Update domain index row
      4. Update any cross-links.md references
      5. Update wiki pages that link to old_slug in their front matter
      6. git commit

    ChromaDB and SQLite caller must update their records separately (see
    vector_store.py and db.py — this function only handles the wiki git repo).
    """
    wiki = _wiki_root()
    old_path = _page_path(domain, old_slug)
    new_path = _page_path(domain, new_slug)

    if not old_path.exists():
        raise FileNotFoundError(f"Wiki page not found: {old_path}")
    if new_path.exists():
        raise FileExistsError(f"Target slug already exists: {new_path}")

    # 1. git mv
    subprocess.run(
        ["git", "-C", str(wiki), "mv", str(old_path.relative_to(wiki)), str(new_path.relative_to(wiki))],
        check=True,
    )

    # 2. Update slug in front matter
    content = new_path.read_text(encoding="utf-8")
    content = re.sub(r"^(slug:\s*)" + re.escape(old_slug) + r"\s*$", f"\\g<1>{new_slug}", content, flags=re.MULTILINE)
    new_path.write_text(content, encoding="utf-8")

    # 3. Update domain index
    idx = _index_path(domain)
    if idx.exists():
        idx_text = idx.read_text(encoding="utf-8")
        idx_text = re.sub(
            r"^\|\s*" + re.escape(old_slug) + r"\s*\|",
            f"| {new_slug} |",
            idx_text,
            flags=re.MULTILINE,
        )
        idx.write_text(idx_text, encoding="utf-8")

    # 4. Update cross-links.md
    cl = _cross_links_path()
    if cl.exists():
        cl_text = cl.read_text(encoding="utf-8")
        cl_text = cl_text.replace(f"| {old_slug} |", f"| {new_slug} |")
        cl.write_text(cl_text, encoding="utf-8")

    # 5. Update any page that has old_slug in its front matter links list
    for page in wiki.glob("domains/*/*.md"):
        if page == new_path or page.name == "index.md":
            continue
        page_text = page.read_text(encoding="utf-8")
        if old_slug in page_text:
            page_text = re.sub(
                r"(^- )" + re.escape(old_slug) + r"(\s*$)",
                f"\\g<1>{new_slug}\\2",
                page_text,
                flags=re.MULTILINE,
            )
            page.write_text(page_text, encoding="utf-8")

    # 6. Stage everything and commit
    subprocess.run(["git", "-C", str(wiki), "add", "-A"], check=True)
    msg = f"rename: {old_slug} → {new_slug}"
    subprocess.run(["git", "-C", str(wiki), "commit", "-m", msg], check=True)


# ---------------------------------------------------------------------------
# Wiki page rendering
# ---------------------------------------------------------------------------

def find_related_article_pages(
    body: str,
    exclude_slug: str = "",
    top_k: int = 3,
    threshold: float = 0.75,
) -> list[str]:
    """Search existing wiki pages for article-type pages semantically related to body.

    Returns up to top_k slugs whose cosine similarity to body exceeds threshold.
    Pages without note_type: article in their front matter are excluded.
    Returns empty list if ChromaDB is unavailable or has no article pages.
    """
    try:
        from vector_store import get_vector_store
        store = get_vector_store()
        results = store.cross_domain_search(body[:2000], n_results=top_k * 3)
    except Exception:
        return []

    related: list[str] = []
    for item in results:
        score = item.get("score", 0.0)
        if score < threshold:
            continue
        meta = item.get("metadata", {})
        slug = meta.get("slug", "")
        domain = meta.get("domain", "")
        if not slug or slug == exclude_slug:
            continue
        # Only include article-type pages
        page_content = read_wiki_page(domain, slug)
        if not page_content:
            continue
        page_meta = _parse_front_matter(page_content)
        if page_meta.get("note_type") != "article":
            continue
        related.append(slug)
        if len(related) >= top_k:
            break

    return related


def render_knowledge_card(llm_output: str, related_slugs: list[str]) -> str:
    """Append ## Related Papers section to LLM-generated knowledge card body if slugs provided."""
    body = llm_output.strip()
    if related_slugs:
        links = "\n".join(f"- [[{s}]]" for s in related_slugs)
        body = body + f"\n\n## Related Papers\n\n{links}"
    return body


def render_knowledge_card_page(
    existing_content: Optional[str],
    slug: str,
    domain: str,
    body: str,
    source_path: str,
    links: list[str],
    languages: list[str],
    confidence: float,
    source_url: Optional[str] = None,
    edited_content: Optional[str] = None,
    note_type: str = "article",
) -> str:
    """Render a full wiki page for an article knowledge card with structured body."""
    if edited_content:
        return edited_content

    today = date.today().isoformat()

    if existing_content:
        meta = _parse_front_matter(existing_content)
        created = meta.get("created", today)
        version = meta.get("version", 1) + 1
        existing_sources = meta.get("sources") or []
        existing_links = meta.get("links") or []
    else:
        created = today
        version = 1
        existing_sources = []
        existing_links = []

    source_slug = "/".join(Path(source_path).parts[-2:])
    sources = list(dict.fromkeys(existing_sources + [source_slug]))
    all_links = list(dict.fromkeys(existing_links + links))

    front_matter: dict = {
        "slug": slug,
        "domain": domain,
        "note_type": note_type,
        "languages": languages,
        "created": created,
        "updated": today,
        "version": version,
        "sources": sources,
        "links": all_links,
        "disputes": [],
        "confidence": round(confidence, 2),
    }
    if source_url:
        front_matter["source_url"] = source_url

    fm_str = yaml.dump(front_matter, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return f"---\n{fm_str}---\n\n{body}\n"


def render_wiki_page(
    existing_content: Optional[str],
    slug: str,
    domain: str,
    summary: str,
    source_path: str,
    links: list[str],
    languages: list[str],
    confidence: float,
    edited_content: Optional[str] = None,
) -> str:
    """Render the full wiki page markdown with YAML front matter."""
    if edited_content:
        return edited_content

    today = date.today().isoformat()

    if existing_content:
        meta = _parse_front_matter(existing_content)
        created = meta.get("created", today)
        version = meta.get("version", 1) + 1
        existing_sources = meta.get("sources") or []
        existing_links = meta.get("links") or []
    else:
        created = today
        version = 1
        existing_sources = []
        existing_links = []

    source_slug = "/".join(Path(source_path).parts[-2:])
    sources = list(dict.fromkeys(existing_sources + [source_slug]))
    all_links = list(dict.fromkeys(existing_links + links))

    front_matter = {
        "slug": slug,
        "domain": domain,
        "languages": languages,
        "created": created,
        "updated": today,
        "version": version,
        "sources": sources,
        "links": all_links,
        "disputes": [],
        "confidence": round(confidence, 2),
    }

    fm_str = yaml.dump(front_matter, allow_unicode=True, default_flow_style=False, sort_keys=False)
    title = slug.replace("-", " ").title()

    if existing_content:
        body_match = re.search(r"^---\n.*?^---\n(.*)$", existing_content, re.DOTALL | re.MULTILINE)
        existing_body = body_match.group(1).strip() if body_match else ""
    else:
        existing_body = ""

    sources_section = "\n".join(f"- [[{s}]]" for s in sources)
    related_section = "\n".join(f"- [[{lk}]]" for lk in all_links)

    body_parts = [f"## {title}\n"]
    if existing_body:
        # Extract only the concept body — everything before the first ## Sources / ## Related
        # Using re.split on section headers is more reliable than a lookahead with re.MULTILINE
        concept_block = re.split(r"\n## (?:Sources|Related)\b", existing_body)[0]
        # Strip the title line (## Title\n) to get just the accumulated content
        concept_content = re.sub(r"^## [^\n]+\n", "", concept_block, count=1).strip()
        if concept_content:
            body_parts.append(concept_content + "\n")

    body_parts.append(f"\n{summary}\n")
    body_parts.append("\n## Sources\n" + sources_section)
    if all_links:
        body_parts.append("\n## Related\n" + related_section)

    return f"---\n{fm_str}---\n\n" + "\n".join(body_parts) + "\n"


def _parse_front_matter(content: str) -> dict:
    """Extract and parse YAML front matter from a markdown page."""
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Wiki store utilities")
    sub = parser.add_subparsers(dest="cmd")

    ren = sub.add_parser("rename", help="Rename a wiki page slug")
    ren.add_argument("domain", help="Domain (e.g. mental-model)")
    ren.add_argument("old_slug", help="Current slug")
    ren.add_argument("new_slug", help="New slug")

    args = parser.parse_args()
    if args.cmd == "rename":
        try:
            rename_wiki_page(args.domain, args.old_slug, args.new_slug)
            print(f"[OK] Renamed {args.domain}/{args.old_slug} → {args.new_slug}")
            print("[NOTE] Update ChromaDB and SQLite manually if needed:")
            print("       uv run python src/vector_store.py --reindex-slug", args.domain, args.new_slug)
            print("       sqlite3 db/brain.sqlite \"UPDATE notes SET wiki_page='" + args.new_slug + "' WHERE wiki_page='" + args.old_slug + "';\"")
        except (FileNotFoundError, FileExistsError) as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()
